"""Held-out coupling prediction (review item P1.4).

The coupling account is currently a post-hoc explanation. This turns it into a predictor
and tests whether it GENERALIZES to unseen image populations: leave-one-corpus-out
cross-validation over the cross-corpus crossover data (e_crosscorpus). For each held-out
corpus we fit the two-term model on the other corpora and predict the held-out cells,
then report mean absolute error and sign-classification accuracy against three baselines
(mean, size-only, fixed-cost-only). If the two-term model beats the baselines on held-out
corpora, the coupling account predicts rather than merely describes.

Cell features (source-computable before building any atlas):
  F   = 100 * H_codec * N / bytes_individual   (fixed-cost amortization term)
  Het = mean pairwise L2 distance of 12x12 tile thumbnails (content heterogeneity)
Target: matched-SSIM-0.97 atlas saving (%).
Model:  saving = a*F - sum_codec b_codec * Het * [codec] + intercept
"""
import json
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
CC = ROOT / "results" / "static" / "e_crosscorpus"
OUT = ROOT / "results" / "static" / "e_heldout"
OUT.mkdir(parents=True, exist_ok=True)
H = {"jpeg": 600, "webp": 30, "avif": 303}
CORP_DIR = {"picsum": ROOT / "assets" / "photos", "flickr": ROOT / "assets_oos" / "flickr",
            "flickr_nature": ROOT / "assets_oos" / "flickr_nature",
            "flickr_food": ROOT / "assets_oos" / "flickr_food"}


def heterogeneity(cdir, n, size):
    files = sorted(p for p in Path(cdir).iterdir()
                   if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"))[:n]
    T = []
    for f in files:
        im = Image.open(f).convert("RGB").resize((12, 12), Image.BILINEAR)
        T.append(np.asarray(im, dtype=np.float32).ravel() / 255.0)
    T = np.stack(T)
    d = np.sqrt(((T[:, None, :] - T[None]) ** 2).sum(-1))
    m = d[np.triu_indices(len(T), 1)].mean()
    return float(m / np.sqrt(T.shape[1]))


def build_cells():
    rows = json.load((CC / "results.json").open())
    het_cache = {}
    cells = []
    for r in rows:
        if r["saving_pct"] is None or r["codec"] not in H:
            continue
        key = (r["corpus"], r["size"])
        if key not in het_cache:
            het_cache[key] = heterogeneity(CORP_DIR[r["corpus"]], r["n"], r["size"])
        cells.append({"corpus": r["corpus"], "size": r["size"], "codec": r["codec"],
                      "F": 100 * H[r["codec"]] * r["n"] / r["bytes_individual"],
                      "Het": het_cache[key], "inv_size": 1.0 / r["size"],
                      "saving": r["saving_pct"]})
    return cells


def fit_predict(train, test, model):
    codecs = sorted(set(c["codec"] for c in train))
    def design(cells):
        cols = []
        if model in ("twoterm", "fixedcost"):
            cols.append([c["F"] for c in cells])
        if model == "twoterm":
            for cc in codecs:
                cols.append([c["Het"] * (c["codec"] == cc) for c in cells])
        if model == "sizeonly":
            cols.append([c["inv_size"] for c in cells])
        cols.append([1.0] * len(cells))
        return np.array(cols).T
    y = np.array([c["saving"] for c in train])
    A = design(train)
    coef, *_ = np.linalg.lstsq(A, y, rcond=None)
    if model == "mean":
        return np.full(len(test), y.mean())
    return design(test) @ coef


def main():
    cells = build_cells()
    corpora = sorted(set(c["corpus"] for c in cells))
    models = ["mean", "sizeonly", "fixedcost", "twoterm"]
    results = {m: {"abs_err": [], "sign_ok": []} for m in models}
    per_fold = []
    for held in corpora:
        train = [c for c in cells if c["corpus"] != held]
        test = [c for c in cells if c["corpus"] == held]
        yt = np.array([c["saving"] for c in test])
        fold = {"held": held, "n_test": len(test)}
        for m in models:
            pred = fit_predict(train, test, m)
            ae = np.abs(pred - yt)
            sign_ok = (np.sign(pred) == np.sign(yt))
            results[m]["abs_err"] += ae.tolist()
            results[m]["sign_ok"] += sign_ok.tolist()
            fold[m] = {"mae": round(float(ae.mean()), 2),
                       "sign_acc": round(float(sign_ok.mean()), 3)}
        per_fold.append(fold)

    summary = {}
    print(f"{'model':10} {'MAE(pp)':>8} {'sign-acc':>9}  (leave-one-corpus-out, "
          f"{len(cells)} cells, {len(corpora)} corpora)")
    for m in models:
        mae = float(np.mean(results[m]["abs_err"]))
        acc = float(np.mean(results[m]["sign_ok"]))
        summary[m] = {"mae": round(mae, 2), "sign_acc": round(acc, 3)}
        print(f"{m:10} {mae:>8.2f} {acc:>9.3f}")
    json.dump({"summary": summary, "per_fold": per_fold, "n_cells": len(cells),
               "corpora": corpora}, (OUT / "results.json").open("w"), indent=1)
    print("HELDOUT DONE")


if __name__ == "__main__":
    main()
