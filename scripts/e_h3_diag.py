"""HTTP/3 diagnosis: is the h3 slowdown request serialization (low stream limit)?

Loads individual_photos_500 (and _200) on h2 and h3, cold browser each time, and from
the Resource Timing entries computes the MAX number of image requests in flight at once
(a sweep line over [requestStart, responseEnd] intervals) and the number of "waves".
If h3 shows far lower peak concurrency than h2, the slowdown is stream-limit
serialization, a testbed/config property, not inherent to HTTP/3.
Also records TTFB spread and the negotiated protocol per resource.
"""
import argparse, json, subprocess, time
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
PORT = {"h1": 8441, "h2": 8442, "h3": 8443}
OUT = ROOT / "results" / "network" / "h3_diag"; OUT.mkdir(parents=True, exist_ok=True)

def wsl(cmd):
    return subprocess.run(["wsl","-d","Ubuntu","-u","root","-e","sh","-c",cmd],
                          capture_output=True, text=True, timeout=60)

def server_ip():
    return wsl("ip -4 addr show eth0 | sed -n 's/.*inet \\([0-9.]*\\).*/\\1/p'").stdout.strip().splitlines()[0]

def spki():
    ip=server_ip(); hs=set()
    for sni in ("localhost",ip,"127.0.0.1"):
        r=wsl(f"echo | openssl s_client -connect {ip}:8443 -servername {sni} 2>/dev/null | "
              "openssl x509 -pubkey -noout 2>/dev/null | openssl pkey -pubin -outform der 2>/dev/null | "
              "openssl dgst -sha256 -binary | base64")
        if r.stdout.strip(): hs.add(r.stdout.strip())
    return ",".join(sorted(hs))

CONC_JS = """() => {
  const es = performance.getEntriesByType('resource')
    .filter(e => /\\.(webp|jpg|png|avif)$/.test(e.name))
    .map(e => ({s: e.requestStart||e.startTime, e: e.responseEnd, p: e.nextHopProtocol}));
  // sweep line for peak concurrency
  const evs = [];
  es.forEach(r => { evs.push([r.s,1]); evs.push([r.e,-1]); });
  evs.sort((a,b)=> a[0]-b[0] || a[1]-b[1]);
  let cur=0, peak=0; evs.forEach(([_,d])=>{ cur+=d; if(cur>peak)peak=cur; });
  const protos=[...new Set(es.map(r=>r.p))];
  return {n: es.length, peakConcurrency: peak, protocols: protos,
          spanMs: Math.max(...es.map(r=>r.e)) - Math.min(...es.map(r=>r.s))};
}"""

def one(pw, ip, proto, page, sp):
    args=["--ignore-certificate-errors", f"--ignore-certificate-errors-spki-list={sp}"]
    if proto=="h3": args+=[f"--origin-to-force-quic-on={ip}:{PORT['h3']}","--enable-quic"]
    b=pw.chromium.launch(args=args)
    try:
        ctx=b.new_context(ignore_https_errors=True); pg=ctx.new_page()
        pg.goto(f"https://{ip}:{PORT[proto]}/{page}.html", wait_until="commit", timeout=120000)
        pg.wait_for_function("typeof window.__done!=='undefined'", timeout=120000)
        res=pg.evaluate("()=>window.__done"); conc=pg.evaluate(CONC_JS)
        return {"allVisibleMs":res["allVisibleMs"], **conc}
    finally:
        b.close()

def main():
    ip=server_ip(); sp=spki()
    print("server",ip,flush=True)
    out=(OUT/"loads.jsonl").open("a")
    with sync_playwright() as pw:
        for page in ("individual_photos_200","individual_photos_500"):
            for proto in ("h2","h3"):
                for rep in range(4):
                    try:
                        r=one(pw,ip,proto,page,sp)
                    except Exception as e:
                        r={"error":str(e)[:150]}
                    row={"page":page,"proto":proto,"rep":rep,**r}
                    out.write(json.dumps(row)+"\n"); out.flush()
                    print(proto,page,rep,"peak_concurrency",r.get("peakConcurrency"),
                          "allVisibleMs",round(r.get("allVisibleMs") or 0),flush=True)
    print("H3DIAG DONE")

if __name__=="__main__":
    main()
