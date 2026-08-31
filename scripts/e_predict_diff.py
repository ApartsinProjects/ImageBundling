"""Codec-differential check (Fable protocol fix): give the source features their best
possible shot. Predict the JPEG-minus-WebP saving per (class, size) from the six source
features, leave-one-class-out. Differencing the two codecs cancels the shared fixed-cost
amortization term F and isolates the adaptive-state coupling penalty, which is exactly
what features like heterogeneity/edge/frequency were chosen to explain. If features cannot
predict even this isolated differential better than a constant, the negative is airtight.
"""
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
CELLS = ROOT / "results" / "static" / "e_predict" / "cells.json"
FEATS = ["edge", "dct_hf", "hist_ent", "uniq", "hetero", "lum_var"]


def main():
    cells = json.load(CELLS.open())
    # pair jpeg and webp within each (class, size)
    by = {}
    for c in cells:
        by.setdefault((c["cls"], c["size"]), {})[c["codec"]] = c
    pairs = []
    for (cls, size), d in by.items():
        if "jpeg" in d and "webp" in d:
            diff = d["jpeg"]["saving"] - d["webp"]["saving"]   # coupling differential
            pairs.append({"cls": cls, "size": size, "diff": diff,
                          **{f: d["jpeg"][f] for f in FEATS}})
    classes = sorted(set(p["cls"] for p in pairs))
    con_ae, rich_ae = [], []
    for held in classes:
        tr = [p for p in pairs if p["cls"] != held]
        te = [p for p in pairs if p["cls"] == held]
        means = [np.mean([p[f] for p in tr]) for f in FEATS]
        stds = [np.std([p[f] for p in tr]) + 1e-9 for f in FEATS]
        y = np.array([p["diff"] for p in tr])
        # constant baseline = train mean
        for p in te:
            con_ae.append(abs(y.mean() - p["diff"]))
        # rich features
        A = np.array([[(p[f] - means[i]) / stds[i] for i, f in enumerate(FEATS)] + [1.0]
                      for p in tr])
        coef, *_ = np.linalg.lstsq(A, y, rcond=None)
        for p in te:
            x = np.array([(p[f] - means[i]) / stds[i] for i, f in enumerate(FEATS)] + [1.0])
            rich_ae.append(abs(float(x @ coef) - p["diff"]))
    out = {"n_pairs": len(pairs), "classes": classes,
           "diff_range": [round(min(p["diff"] for p in pairs), 1),
                          round(max(p["diff"] for p in pairs), 1)],
           "constant_mae": round(float(np.mean(con_ae)), 2),
           "rich_features_mae": round(float(np.mean(rich_ae)), 2)}
    out["verdict"] = ("features help" if out["rich_features_mae"] < 0.8 * out["constant_mae"]
                      else "features do NOT beat a constant on the isolated coupling differential")
    json.dump(out, (ROOT / "results" / "static" / "e_predict" / "diff.json").open("w"), indent=1)
    print(json.dumps(out, indent=1))
    print("DIFF DONE")


if __name__ == "__main__":
    main()
