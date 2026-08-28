"""Aggregate Phase 1 static-study results: bytes saved by atlasing at matched quality.

For each (class, n, codec_family, mode/pad), build the rate-distortion curve over the
quality ladder (ssim_mean vs bytes_total), then interpolate bytes at fixed SSIM targets
so atlas and individual are compared at equal quality. Lossless codecs compare directly.

Usage: python aggregate_static.py --tag run1 [--ssim-targets 0.95,0.97,0.99]
"""
import argparse
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
LOSSLESS = {"png", "webp_ll", "jxl_ll"}


def bytes_at_ssim(points, target):
    """Log-linear interpolation of bytes at a target ssim. points: [(ssim, bytes)]."""
    pts = sorted(points)
    ss = np.array([p[0] for p in pts])
    bb = np.log(np.array([float(p[1]) for p in pts]))
    if target < ss[0] or target > ss[-1]:
        return None
    return float(np.exp(np.interp(target, ss, bb)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--ssim-targets", default="0.95,0.97,0.99")
    args = ap.parse_args()
    targets = [float(x) for x in args.ssim_targets.split(",")]

    rows = [json.loads(l) for l in
            (ROOT / "results" / "static" / args.tag / "results.jsonl").open()]

    # group: (class, n, codec) -> (mode, pad) -> list of (ssim, bytes)
    groups = defaultdict(lambda: defaultdict(list))
    for r in rows:
        groups[(r["class"], r["n"], r["codec"])][(r["mode"], r["pad"])].append(
            (r["ssim_mean"], r["bytes_total"]))

    out = []
    for (cls, n, codec), conds in sorted(groups.items()):
        ind = conds.get(("individual", 0))
        if not ind:
            continue
        for (mode, pad), pts in sorted(conds.items()):
            if mode == "individual":
                continue
            if codec in LOSSLESS:
                b_ind, b_atl = ind[0][1], pts[0][1]
                out.append({"class": cls, "n": n, "codec": codec, "pad": pad,
                            "ssim_target": None, "bytes_individual": b_ind,
                            "bytes_atlas": b_atl,
                            "saving_pct": round(100 * (1 - b_atl / b_ind), 2)})
            else:
                for t in targets:
                    b_ind = bytes_at_ssim(ind, t)
                    b_atl = bytes_at_ssim(pts, t)
                    bound = False
                    # Atlas ladder entirely above target: its lowest-quality point
                    # OVERSTATES bytes-at-target, so using it understates the saving.
                    # Report as a conservative lower bound. Same logic for individual.
                    if b_atl is None and min(p[0] for p in pts) > t:
                        b_atl, bound = float(sorted(pts)[0][1]), True
                    if b_ind is None and min(p[0] for p in ind) > t:
                        b_ind = float(sorted(ind)[0][1])  # overstates -> saving not a bound anymore
                        bound = None  # ambiguous direction; skip
                    if b_ind is None or b_atl is None or bound is None:
                        continue
                    out.append({"class": cls, "n": n, "codec": codec, "pad": pad,
                                "ssim_target": t, "lower_bound": bound,
                                "bytes_individual": round(b_ind),
                                "bytes_atlas": round(b_atl),
                                "saving_pct": round(100 * (1 - b_atl / b_ind), 2)})

    outfile = ROOT / "results" / "static" / args.tag / "matched_quality_savings.json"
    json.dump(out, outfile.open("w"), indent=1)

    # human-readable summary: best padding per (class, n, codec) at middle target
    print(f"{'class':8} {'n':>4} {'codec':8} {'pad':>3} {'ssim':>5} "
          f"{'indiv B':>10} {'atlas B':>10} {'saving':>8}")
    for r in out:
        print(f"{r['class']:8} {r['n']:>4} {r['codec']:8} {r['pad']:>3} "
              f"{str(r['ssim_target']):>5} {r['bytes_individual']:>10} "
              f"{r['bytes_atlas']:>10} {r['saving_pct']:>7.1f}%")
    print(f"\nwrote {outfile}")


if __name__ == "__main__":
    main()
