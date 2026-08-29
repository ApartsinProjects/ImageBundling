"""HTTP/3 under-multiplexing, confirmed from the server's own QUIC transport log.

The network study's h3 slowdown was diagnosed from browser Resource Timing (peak images
in flight). This script confirms it directly from quic-go's qlog on the server, which
removes the reliance on client-side reconstruction. For each cold h3 load we clear the
qlog dir, run the load, and parse the single .sqlog the connection produced for:
  - peak_concurrency: max simultaneously-open request streams (client-bidi, id%4==0),
    from a sweep line over [request headers parsed, last response frame created];
  - max_streams / initial_max_streams_bidi: the stream ceiling the SERVER advertises.
If the server advertises ~100 streams while the peak concurrency stays ~6, the
under-multiplexing is imposed by the client's QUIC scheduler, not the server config,
and is a deployment property rather than anything inherent to HTTP/3.

qlog is QUIC-only, so h2 (TCP) carries no server trace; its peak concurrency is the
browser-side number, reported for contrast.
"""
import json
import subprocess
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "results" / "network" / "h3_qlog"
OUT.mkdir(parents=True, exist_ok=True)
PORT = {"h2": 8442, "h3": 8443}
PAGES = ["individual_photos_500", "atlas1_photos_500", "individual_emoji_500"]
REPS = 6

# server-side qlog parser, run under WSL python3 against the one .sqlog per load
PARSER = r'''
import sys, json, glob
files = glob.glob("/root/qlog/*.sqlog")
if not files:
    print(json.dumps({"error": "no sqlog"})); sys.exit()
path = max(files, key=lambda f: __import__("os").path.getmtime(f))
reqs = {}          # stream_id -> [start, end]
ms = []            # (time, maximum) bidirectional MAX_STREAMS
init_bidi = None
with open(path) as f:
    for line in f:
        line = line.strip().strip("\x1e")
        if not line:
            continue
        try:
            e = json.loads(line)
        except Exception:
            continue
        t = e.get("time"); n = e.get("name"); d = e.get("data", {}) or {}
        if n == "transport:parameters_set":
            v = d.get("initial_max_streams_bidi")
            if v is not None:
                init_bidi = v
        elif n == "http3:frame_parsed":
            sid = d.get("stream_id"); fr = d.get("frame", {}) or {}
            if fr.get("frame_type") == "headers" and sid is not None and sid % 4 == 0:
                reqs.setdefault(sid, [t, t])
                reqs[sid][0] = min(reqs[sid][0], t)
        elif n == "http3:frame_created":
            sid = d.get("stream_id")
            if sid is not None and sid % 4 == 0 and sid in reqs:
                reqs[sid][1] = max(reqs[sid][1], t)
        for fr in d.get("frames", []) or []:
            if fr.get("frame_type") == "max_streams" and fr.get("stream_type") == "bidirectional":
                ms.append((t, fr.get("maximum")))
evs = []
for sid, (s, e2) in reqs.items():
    evs.append((s, 1)); evs.append((e2, -1))
evs.sort(key=lambda x: (x[0], x[1]))
cur = peak = 0
for _, delta in evs:
    cur += delta; peak = max(peak, cur)
print(json.dumps({
    "sqlog": __import__("os").path.basename(path),
    "n_request_streams": len(reqs),
    "server_peak_concurrency": peak,
    "initial_max_streams_bidi": init_bidi,
    "max_streams_first": ms[0][1] if ms else None,
    "max_streams_last": ms[-1][1] if ms else None,
}))
'''

CONC_JS = r"""() => {
  const es = performance.getEntriesByType('resource')
    .filter(e => /\.(webp|jpg|png)$/.test(e.name))
    .map(e => ({s: e.requestStart||e.startTime, e: e.responseEnd, p: e.nextHopProtocol}));
  const evs = [];
  es.forEach(r => { evs.push([r.s,1]); evs.push([r.e,-1]); });
  evs.sort((a,b)=> a[0]-b[0] || a[1]-b[1]);
  let cur=0, peak=0; evs.forEach(([_,d])=>{ cur+=d; if(cur>peak)peak=cur; });
  return {n: es.length, browserPeak: peak, protocols: [...new Set(es.map(r=>r.p))]};
}"""


def wsl(cmd, timeout=60):
    return subprocess.run(["wsl", "-d", "Ubuntu", "-u", "root", "-e", "sh", "-c", cmd],
                          capture_output=True, text=True, timeout=timeout)


def wsl_py(script, timeout=120):
    return subprocess.run(["wsl", "-d", "Ubuntu", "-u", "root", "-e", "python3", "-c", script],
                          capture_output=True, text=True, timeout=timeout)


def restart_qlog_server():
    wsl("rm -rf /root/qlog && mkdir -p /root/qlog; caddy stop >/dev/null 2>&1; "
        "sleep 1; QLOGDIR=/root/qlog caddy start --config /root/Caddyfile "
        ">/tmp/caddy.log 2>&1; sleep 2")


def spki(ip):
    hs = set()
    for sni in ("localhost", ip, "127.0.0.1"):
        r = wsl(f"echo | openssl s_client -connect {ip}:8443 -servername {sni} 2>/dev/null | "
                "openssl x509 -pubkey -noout 2>/dev/null | openssl pkey -pubin -outform der "
                "2>/dev/null | openssl dgst -sha256 -binary | base64")
        if r.stdout.strip():
            hs.add(r.stdout.strip())
    return ",".join(sorted(hs))


def load(pw, ip, proto, page, sp):
    args = ["--ignore-certificate-errors", f"--ignore-certificate-errors-spki-list={sp}"]
    if proto == "h3":
        args += [f"--origin-to-force-quic-on={ip}:{PORT['h3']}", "--enable-quic"]
    b = pw.chromium.launch(args=args)
    try:
        ctx = b.new_context(ignore_https_errors=True)
        pg = ctx.new_page()
        pg.goto(f"https://{ip}:{PORT[proto]}/{page}.html", wait_until="commit", timeout=120000)
        pg.wait_for_function("typeof window.__done!=='undefined'", timeout=120000)
        d = pg.evaluate("()=>window.__done")
        conc = pg.evaluate(CONC_JS)
        return {"allVisibleMs": d["allVisibleMs"], **conc}
    finally:
        b.close()


def main():
    restart_qlog_server()
    ip = wsl("hostname -I").stdout.strip().split()[0]
    sp = spki(ip)
    print(f"server {ip}, {len(sp.split(','))} spki hashes", flush=True)
    rows = []
    with sync_playwright() as pw:
        for page in PAGES:
            for proto in ("h2", "h3"):
                for rep in range(REPS):
                    if proto == "h3":
                        wsl("rm -f /root/qlog/*.sqlog")
                    try:
                        r = load(pw, ip, proto, page, sp)
                    except Exception as e:
                        rows.append({"page": page, "proto": proto, "rep": rep,
                                     "error": str(e)[:150]})
                        print(proto, page, rep, "ERROR", str(e)[:80], flush=True)
                        continue
                    row = {"page": page, "proto": proto, "rep": rep,
                           "allVisibleMs": round(r["allVisibleMs"]),
                           "browser_peak": r["browserPeak"], "protocols": r["protocols"]}
                    if proto == "h3":
                        pr = wsl_py(PARSER)
                        try:
                            row.update(json.loads(pr.stdout.strip()))
                        except Exception:
                            row["qlog_error"] = pr.stdout[:100] + pr.stderr[:100]
                    rows.append(row)
                    print(proto, page, rep, "browser_peak", row.get("browser_peak"),
                          "server_peak", row.get("server_peak_concurrency"),
                          "max_streams", row.get("initial_max_streams_bidi"),
                          "ms", row["allVisibleMs"], flush=True)
                    json.dump(rows, (OUT / "results.json").open("w"), indent=1)
                    time.sleep(1.5)  # let Chromium processes reap (avoids ERR_INSUFFICIENT_RESOURCES)
    # keep one representative h3 trace
    wsl("cp $(ls -t /root/qlog/*.sqlog 2>/dev/null | head -1) /root/qlog/representative.sqlog "
        "2>/dev/null || true")
    print("H3QLOG DONE", flush=True)


if __name__ == "__main__":
    main()
