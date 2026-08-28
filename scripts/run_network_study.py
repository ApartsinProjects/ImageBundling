"""Phase 2 harness: drive Chromium over the WSL2 Caddy server under netem shaping.

Each load: fresh browser process (cold connections, cold cache), navigate, await the
page's window.__done promise, record {allVisibleMs, per-resource transfer+protocol}.

Usage:
  python run_network_study.py --tag smoke --pages atlas1_emoji_50,individual_emoji_50 \
      --protocols h1,h2,h3 --profiles localhost --reps 2
"""
import argparse
import json
import subprocess
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
PORT = {"h1": 8441, "h2": 8442, "h3": 8443}
EXPECT_PROTO = {"h1": "http/1.1", "h2": "h2", "h3": "h3"}

# name: (delay_ms, rate_mbit, loss_pct); shaping applies to server->client (egress)
PROFILES = {
    "localhost": None,
    "fast": (20, 100, 0),
    "cell4g": (60, 9, 0),
    "slow3g": (150, 1.6, 0),
    "lossy4g": (60, 9, 1),
}


def wsl(cmd):
    return subprocess.run(["wsl", "-d", "Ubuntu", "-u", "root", "-e", "sh", "-c", cmd],
                          capture_output=True, text=True, timeout=60)


def get_server_ip():
    r = wsl("ip -4 addr show eth0 | sed -n 's/.*inet \\([0-9.]*\\).*/\\1/p'")
    return r.stdout.strip().splitlines()[0]


def get_spki():
    """SPKI hash of the served leaf cert; QUIC ignores --ignore-certificate-errors
    but honors --ignore-certificate-errors-spki-list. Caddy's internal leaf rotates,
    so compute at harness start."""
    ip = get_server_ip()
    hashes = set()
    for sni in ("localhost", ip, "127.0.0.1"):
        r = wsl(f"echo | openssl s_client -connect {ip}:8443 -servername {sni} 2>/dev/null | "
                "openssl x509 -pubkey -noout 2>/dev/null | "
                "openssl pkey -pubin -outform der 2>/dev/null | "
                "openssl dgst -sha256 -binary | base64")
        h = r.stdout.strip()
        if h:
            hashes.add(h)
    return ",".join(sorted(hashes))


def set_netem(profile):
    wsl("tc qdisc del dev eth0 root 2>/dev/null; true")
    p = PROFILES[profile]
    if p:
        delay, rate, loss = p
        cmd = f"tc qdisc add dev eth0 root netem delay {delay}ms rate {rate}mbit"
        if loss:
            cmd += f" loss {loss}%"
        r = wsl(cmd)
        if r.returncode != 0:
            raise RuntimeError(f"netem failed: {r.stderr}")


def one_load(pw, ip, proto, page_name, spki, timeout_s=120):
    args = ["--ignore-certificate-errors",
            f"--ignore-certificate-errors-spki-list={spki}"]
    if proto == "h3":
        args += [f"--origin-to-force-quic-on={ip}:{PORT['h3']}", "--enable-quic"]
    browser = pw.chromium.launch(args=args)
    try:
        ctx = browser.new_context(ignore_https_errors=True)
        pg = ctx.new_page()
        url = f"https://{ip}:{PORT[proto]}/{page_name}.html"
        t0 = time.perf_counter()
        pg.goto(url, wait_until="commit", timeout=timeout_s * 1000)
        pg.wait_for_function("typeof window.__done !== 'undefined'",
                             timeout=timeout_s * 1000)
        res = pg.evaluate("() => window.__done", None)
        wall = time.perf_counter() - t0
        protos = {r["protocol"] for r in res["resources"]}
        return {"allVisibleMs": res["allVisibleMs"], "wall_s": round(wall, 3),
                "nRendered": res["nRendered"],
                "bytes": sum(r["transferSize"] for r in res["resources"]),
                "nres": len(res["resources"]), "protocols": sorted(protos)}
    finally:
        browser.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--pages", required=True)
    ap.add_argument("--protocols", default="h1,h2,h3")
    ap.add_argument("--profiles", default="localhost")
    ap.add_argument("--reps", type=int, default=10)
    args = ap.parse_args()

    ip = get_server_ip()
    spki = get_spki()
    print("server ip:", ip, "spki:", spki)
    outdir = ROOT / "results" / "network" / args.tag
    outdir.mkdir(parents=True, exist_ok=True)
    out = (outdir / "loads.jsonl").open("a")

    with sync_playwright() as pw:
        for profile in args.profiles.split(","):
            set_netem(profile)
            try:
                for proto in args.protocols.split(","):
                    for page_name in args.pages.split(","):
                        for rep in range(args.reps):
                            try:
                                r = one_load(pw, ip, proto, page_name, spki)
                                ok = EXPECT_PROTO[proto] in r["protocols"] and len(r["protocols"]) == 1
                            except Exception as e:
                                r, ok = {"error": str(e)[:200]}, False
                            row = {"profile": profile, "proto": proto, "page": page_name,
                                   "rep": rep, "proto_ok": ok, **r}
                            out.write(json.dumps(row) + "\n")
                            out.flush()
                            print(profile, proto, page_name, rep,
                                  r.get("allVisibleMs"), r.get("protocols"), flush=True)
            finally:
                set_netem("localhost")  # always clear shaping
    print("done")


if __name__ == "__main__":
    main()
