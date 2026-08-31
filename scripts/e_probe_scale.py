"""Probe-vs-N scaling (review-prescribed): the probe was validated only at N=50, where a
20-tile pilot is 40% of the group. Its value is the large-N regime where 20 tiles is a few
percent. Fix k=20 and vary N in {50,100,200,500} on three classes x two codecs; does the
probe still forecast the full-N saving? Pre-stated success: fitted-MAE <= 3 pp AND
Spearman >= 0.9 at N=500. If a raw N-bias appears (a k-tile atlas amortizes fixed cost
over fewer tiles than an N-tile one), an analytic fixed-cost correction from the two
individual-byte totals should restore it, else the probe is scoped to N <= ~100.
"""
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image

import e_predict as ep

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "results" / "static" / "e_probe_scale"
OUT.mkdir(parents=True, exist_ok=True)
SIZE = 112
KPROBE = 20
NS = [50, 100, 200, 500]
CLASSES = ["photos", "emoji", "product_white"]
CODECS = ["jpeg", "webp"]


def load(cls, n):
    if cls == "product_white":
        return [ep.synth_product_white(SIZE) for _ in range(n)]
    d = ROOT / "assets" / ("photos" if cls == "photos" else "emoji")
    files = sorted(p for p in d.iterdir()
                   if p.suffix.lower() in (".jpg", ".jpeg", ".png"))[:n]
    out = []
    for f in files:
        im = Image.open(f)
        if im.mode in ("RGBA", "LA", "P"):
            im = Image.alpha_composite(Image.new("RGBA", im.size, (255,) * 4),
                                       im.convert("RGBA"))
        out.append(np.asarray(im.convert("RGB").resize((SIZE, SIZE), Image.LANCZOS)))
    return out


def main():
    cells = []
    for cls in CLASSES:
        tiles_all = load(cls, max(NS))
        for n in NS:
            tiles = tiles_all[:n]
            for codec in CODECS:
                full = ep.saving(tiles, codec)[0][0]
                probe = ep.saving(tiles[:KPROBE], codec)[0][0]
                cells.append({"cls": cls, "n": n, "codec": codec,
                              "full": full, "probe20": probe, "bias": round(probe - full, 2)})
                print(f"  {cls:14} N={n:>3} {codec:5} full={full:+.1f} probe20={probe:+.1f} "
                      f"bias={probe-full:+.1f}", flush=True)
    json.dump(cells, (OUT / "cells.json").open("w"), indent=1)

    def mae_spearman(pred, act):
        pred, act = np.array(pred), np.array(act)
        ra, rp = np.argsort(np.argsort(act)), np.argsort(np.argsort(pred))
        return float(np.mean(np.abs(pred - act))), float(np.corrcoef(ra, rp)[0, 1])

    summary = {"by_N": {}}
    print("\n=== probe20 vs full, by N ===")
    for n in NS:
        rows = [c for c in cells if c["n"] == n]
        full = [c["full"] for c in rows]; prb = [c["probe20"] for c in rows]
        # fitted: one global linear correction full ~ a*probe + b (leave-one-out over the
        # 6 cells at this N would be too few; use pooled fit across all N for the line)
        direct_mae, sp = mae_spearman(prb, full)
        summary["by_N"][n] = {"direct_mae": round(direct_mae, 2), "spearman": round(sp, 3),
                              "mean_bias": round(float(np.mean(np.array(prb) - np.array(full))), 2)}
        print(f"  N={n:>3}: direct-MAE {direct_mae:.2f}  Spearman {sp:.3f}  "
              f"mean-bias {summary['by_N'][n]['mean_bias']:+.2f}")
    # global linear correction fitted on ALL cells (probe -> full), report residual at N=500
    P = np.array([[c["probe20"], 1.0] for c in cells]); Y = np.array([c["full"] for c in cells])
    coef, *_ = np.linalg.lstsq(P, Y, rcond=None)
    r500 = [c for c in cells if c["n"] == 500]
    pred500 = np.array([coef[0] * c["probe20"] + coef[1] for c in r500])
    act500 = np.array([c["full"] for c in r500])
    fit_mae500, sp500 = float(np.mean(np.abs(pred500 - act500))), None
    ra, rp = np.argsort(np.argsort(act500)), np.argsort(np.argsort(pred500))
    sp500 = float(np.corrcoef(ra, rp)[0, 1])
    summary["fitted_N500"] = {"mae": round(fit_mae500, 2), "spearman": round(sp500, 3),
                              "line": [round(float(coef[0]), 3), round(float(coef[1]), 2)]}
    ok = fit_mae500 <= 3.0 and sp500 >= 0.9
    summary["verdict"] = ("PROBE VALID AT N=500" if ok else
                          "probe needs N-correction or scope to small N")
    print(f"\n  fitted probe->full at N=500: MAE {fit_mae500:.2f}  Spearman {sp500:.3f}")
    print(f"  pre-stated bar: MAE<=3 AND Spearman>=0.9  ->  {summary['verdict']}")
    json.dump(summary, (OUT / "results.json").open("w"), indent=1)
    print("PROBE-SCALE DONE")


if __name__ == "__main__":
    main()
