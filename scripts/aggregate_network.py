"""Aggregate Phase 2 network sweep: median time-to-all-visible per cell.

Usage: python aggregate_network.py --tag phase2_full
Writes results/network/<tag>/summary.json and prints a per-profile table of medians
(ms) for individual vs atlas1 vs atlas4, plus the speedup ratio individual/atlas1.
"""
import argparse
import json
import statistics as st
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--drop-first", type=int, default=1,
                    help="drop first rep per cell (cold-start outlier)")
    args = ap.parse_args()
    rows = [json.loads(l) for l in
            (ROOT / "results" / "network" / args.tag / "loads.jsonl").open()]

    ok = [r for r in rows if r.get("allVisibleMs") and r.get("proto_ok")]
    bad_proto = [r for r in rows if r.get("allVisibleMs") and not r.get("proto_ok")]
    errs = [r for r in rows if not r.get("allVisibleMs")]
    print(f"{len(rows)} loads: {len(ok)} ok, {len(bad_proto)} wrong-protocol, "
          f"{len(errs)} errors")

    cells = defaultdict(list)
    for r in ok:
        if r["rep"] < args.drop_first:
            continue
        cls = "emoji" if "emoji" in r["page"] else "photos"
        n = int(r["page"].rsplit("_", 1)[1])
        cond = r["page"].split("_")[0]
        cells[(r["profile"], r["proto"], cls, n, cond)].append(r["allVisibleMs"])

    summary = []
    for k, v in sorted(cells.items()):
        summary.append({"profile": k[0], "proto": k[1], "cls": k[2], "n": k[3],
                        "cond": k[4], "median_ms": round(st.median(v), 1),
                        "p25": round(st.quantiles(v, n=4)[0], 1),
                        "p75": round(st.quantiles(v, n=4)[2], 1), "n_loads": len(v)})
    json.dump(summary, (ROOT / "results" / "network" / args.tag /
                        "summary.json").open("w"), indent=1)

    med = {(s["profile"], s["proto"], s["cls"], s["n"], s["cond"]): s["median_ms"]
           for s in summary}
    print(f"\n{'profile':10}{'proto':6}{'cls':7}{'n':>4} {'individ':>9} {'atlas1':>8} "
          f"{'atlas4':>8} {'bundle':>8} {'atl-x':>6} {'bun-x':>6}")
    for profile in ["localhost", "fast", "cell4g", "slow3g", "lossy4g"]:
        for proto in ["h1", "h2", "h3"]:
            for cls in ["emoji", "photos"]:
                for n in [10, 50, 200, 500]:
                    i = med.get((profile, proto, cls, n, "individual"))
                    a1 = med.get((profile, proto, cls, n, "atlas1"))
                    a4 = med.get((profile, proto, cls, n, "atlas4"))
                    bb = med.get((profile, proto, cls, n, "bundlebin"))
                    if i is None or a1 is None:
                        continue
                    print(f"{profile:10}{proto:6}{cls:7}{n:>4} {i:>9.0f} {a1:>8.0f} "
                          f"{a4 if a4 else 0:>8.0f} {bb if bb else 0:>8.0f} "
                          f"{i/a1:>5.1f}x {i/bb if bb else 0:>5.1f}x")


if __name__ == "__main__":
    main()
