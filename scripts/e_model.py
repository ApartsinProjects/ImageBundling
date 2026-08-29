"""Two-term coupling model: predict atlas saving from source-computable features.

The paper's fixed-cost law (saving ~ overhead/content ratio) is R^2=0.99 for JPEG but
fails for WebP/PNG because it omits the adaptive-state penalty. Here we make that second
term measurable and fit a predictive model that works ACROSS codecs.

Features per cell (all computable from the source tiles + one individual encode, i.e.
before building any atlas):
  F   = fixed-cost term      = 100 * H_codec * N / bytes_individual
  Het = content heterogeneity = mean pairwise L2 distance of 12x12 tile thumbnails
                                (normalized 0..1), a proxy for how much a shared codec
                                model must compromise across tiles.
Model:  saving = a*F  -  b_codec * Het    (adaptive penalty scaled per codec)
Compare pooled R^2 of the two-term model vs the fixed-cost-only model.
"""
import json, io, math
from pathlib import Path
import numpy as np
from PIL import Image
import static_study as ss

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "results" / "static" / "e_model"; OUT.mkdir(parents=True, exist_ok=True)
H = {"jpeg": 600, "webp": 30, "png": 67, "webp_ll": 30}
CLASSES = [("phase1_emoji", "emoji", None), ("phase1_photos", "photos", None),
           ("phase1_photos112", "photos", 112), ("phase1_photos56", "photos", 56)]


def thumbs(tiles, s=12):
    return np.stack([np.asarray(Image.fromarray(t).resize((s, s), Image.BILINEAR),
                                dtype=np.float32).ravel() for t in tiles])


def heterogeneity(tiles):
    """mean pairwise L2 distance of normalized 12x12 thumbnails, scaled to ~0..1."""
    T = thumbs(tiles) / 255.0
    n = len(T)
    idx = np.random.default_rng(0).choice(n, min(n, 80), replace=False)  # sample for speed
    T = T[idx]
    d = np.sqrt(((T[:, None, :] - T[None]) ** 2).sum(-1))
    m = d[np.triu_indices(len(T), 1)].mean()
    return float(m / np.sqrt(T.shape[1]))  # normalize by sqrt(dim) -> ~0..1


def load_tiles(cls, size):
    tiles = []
    for f in sorted((ROOT / "assets" / cls).iterdir())[:500]:
        im = Image.open(f)
        if im.mode in ("RGBA", "LA", "P"):
            im = Image.alpha_composite(Image.new("RGBA", im.size, (255,)*4), im.convert("RGBA"))
        im = im.convert("RGB")
        if size and im.width != size:
            im = im.resize((size, size), Image.LANCZOS)
        tiles.append(np.asarray(im))
    return tiles


# build cell table
cells = []
het_cache = {}
for tag, cls, size in CLASSES:
    r = json.load(open(ROOT / "results" / "static" / tag / "matched_quality_savings.json"))
    tiles_all = load_tiles(cls, size)
    for x in r:
        if x["pad"] != 0 or x["ssim_target"] not in (0.97, None):
            continue
        if x["codec"] not in H:
            continue
        N = x["n"]
        key = (tag, N)
        if key not in het_cache:
            het_cache[key] = heterogeneity(tiles_all[:N])
        cells.append({"codec": x["codec"], "N": N, "class": f"{cls}{size or ''}",
                      "F": 100 * H[x["codec"]] * N / x["bytes_individual"],
                      "Het": het_cache[key], "saving": x["saving_pct"]})

codecs = sorted(set(c["codec"] for c in cells))
F = np.array([c["F"] for c in cells])
Het = np.array([c["Het"] for c in cells])
y = np.array([c["saving"] for c in cells])
cod = np.array([c["codec"] for c in cells])


def r2(pred):
    ss_res = ((y - pred) ** 2).sum(); ss_tot = ((y - y.mean()) ** 2).sum()
    return 1 - ss_res / ss_tot


# model 1: fixed-cost only (a*F + intercept)
A1 = np.vstack([F, np.ones_like(F)]).T
c1, *_ = np.linalg.lstsq(A1, y, rcond=None)
r2_fixed = r2(A1 @ c1)

# model 2: two-term, per-codec penalty on Het  (a*F + sum_codec b_c*Het*[codec] + int)
cols = [F]
names = ["a*F"]
for cc in codecs:
    cols.append(Het * (cod == cc))
    names.append(f"penalty[{cc}]*Het")
cols.append(np.ones_like(F))
A2 = np.vstack(cols).T
c2, *_ = np.linalg.lstsq(A2, y, rcond=None)
r2_two = r2(A2 @ c2)

out = {"n_cells": len(cells), "codecs": codecs,
       "r2_fixed_cost_only": round(float(r2_fixed), 3),
       "r2_two_term": round(float(r2_two), 3),
       "coef_F": round(float(c2[0]), 3),
       "penalty_per_codec": {cc: round(float(c2[1 + i]), 2) for i, cc in enumerate(codecs)},
       "het_range": [round(float(Het.min()), 3), round(float(Het.max()), 3)]}
json.dump({"summary": out, "cells": cells}, (OUT / "results.json").open("w"), indent=1)
print(json.dumps(out, indent=1))
print("MODEL DONE")
