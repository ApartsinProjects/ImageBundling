"""Cross-class predictive model: do cheap source features predict the atlas byte-saving
sign/magnitude across content classes better than a size-and-codec baseline?

The coupling account is descriptive. This tests whether it can be made PREDICTIVE from
features computable before any atlas is built. We assemble content classes with
deliberately diverse image statistics (natural + synthetic extremes), measure the
matched-quality atlas saving per (class, size, codec), extract per-set features, and run
leave-one-CLASS-out cross-validation: a rich-feature model vs a size+codec baseline.

Pre-stated success criterion (declared before running): the rich model counts as a win
only if, on held-out classes, its MAE is below 0.8x the baseline's AND its sign-accuracy
is strictly higher. Otherwise it is an honest negative reinforcing "measure, don't
predict."

Features (all source-computable, cheap): edge density (Sobel), DCT high-frequency energy
ratio, color-histogram entropy, mean unique colors per tile, inter-tile heterogeneity,
luminance variance. Plus the fixed-cost term F = 100*H*N/bytes_individual and 1/size.
"""
import io
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "results" / "static" / "e_predict"
OUT.mkdir(parents=True, exist_ok=True)
SIZES = [56, 112, 224]
CODECS = ["jpeg", "webp"]
H = {"jpeg": 600, "webp": 30}
QUALITIES = [30, 50, 65, 80, 90]
N = 50
TARGET = 0.97
RNG = np.random.default_rng(0)

NATURAL = {
    "photos": ROOT / "assets" / "photos",
    "emoji": ROOT / "assets" / "emoji",
    "flags": ROOT / "assets_oos" / "flags",
    "robo": ROOT / "assets_oos" / "robo",
}


# ---------------- synthetic classes (extreme feature profiles) ----------------

def synth_gradient(sz):
    a, b = RNG.integers(0, 255, 3), RNG.integers(0, 255, 3)
    t = np.linspace(0, 1, sz)[None, :, None] if RNG.random() < 0.5 else np.linspace(0, 1, sz)[:, None, None]
    return (a * (1 - t) + b * t).astype(np.uint8) * np.ones((sz, sz, 3), np.uint8)


def synth_noise(sz):
    return RNG.integers(0, 256, (sz, sz, 3), dtype=np.uint8)


def synth_ui(sz):
    im = Image.new("RGB", (sz, sz), (245, 246, 248))
    d = ImageDraw.Draw(im)
    pal = [(52, 120, 246), (30, 34, 40), (200, 60, 60), (240, 200, 40), (255, 255, 255)]
    for _ in range(RNG.integers(3, 7)):
        x0, y0 = RNG.integers(0, sz - 8, 2)
        x1, y1 = min(sz, x0 + RNG.integers(6, sz // 2)), min(sz, y0 + RNG.integers(4, sz // 3))
        d.rectangle([x0, y0, x1, y1], fill=tuple(pal[RNG.integers(0, len(pal))]))
    for _ in range(RNG.integers(4, 10)):  # text-like bars
        y = RNG.integers(0, sz); x0 = RNG.integers(0, sz // 2)
        d.line([x0, y, min(sz, x0 + RNG.integers(6, sz // 2)), y], fill=(40, 44, 52), width=1)
    return np.asarray(im)


def synth_product_white(sz):
    im = Image.new("RGB", (sz, sz), (255, 255, 255))
    d = ImageDraw.Draw(im)
    c = tuple(int(x) for x in RNG.integers(30, 220, 3))
    m = sz // 4
    if RNG.random() < 0.5:
        d.ellipse([m, m, sz - m, sz - m], fill=c)
    else:
        d.rectangle([m, m, sz - m, sz - m], fill=c)
    return np.asarray(im)


SYNTH = {"gradients": synth_gradient, "noise": synth_noise,
         "ui_mock": synth_ui, "product_white": synth_product_white}


def load_tiles(cls, size):
    if cls in NATURAL:
        d = NATURAL[cls]
        files = sorted(p for p in d.iterdir()
                       if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"))[:N]
        out = []
        for f in files:
            im = Image.open(f)
            if im.mode in ("RGBA", "LA", "P"):
                im = Image.alpha_composite(Image.new("RGBA", im.size, (255,) * 4),
                                           im.convert("RGBA"))
            out.append(np.asarray(im.convert("RGB").resize((size, size), Image.LANCZOS)))
        return out
    gen = SYNTH[cls]
    return [gen(size) for _ in range(N)]


# ---------------- SSIM + encode (matched-quality saving) ----------------

def _box(x, w):
    c = np.cumsum(np.cumsum(x, 0), 1); c = np.pad(c, ((1, 0), (1, 0)))
    return (c[w:, w:] - c[:-w, w:] + c[:-w, :-w] - c[w:, :-w]) / (w * w)


def ssim(a, b, window=8):
    ya = (0.299 * a[..., 0] + 0.587 * a[..., 1] + 0.114 * a[..., 2]).astype(np.float64)
    yb = (0.299 * b[..., 0] + 0.587 * b[..., 1] + 0.114 * b[..., 2]).astype(np.float64)
    w = min(window, ya.shape[0], ya.shape[1])
    C1, C2 = (0.01 * 255) ** 2, (0.03 * 255) ** 2
    ma, mb = _box(ya, w), _box(yb, w)
    vaa = _box(ya * ya, w) - ma * ma; vbb = _box(yb * yb, w) - mb * mb
    vab = _box(ya * yb, w) - ma * mb
    s = ((2 * ma * mb + C1) * (2 * vab + C2)) / ((ma * ma + mb * mb + C1) * (vaa + vbb + C2))
    return float(s.mean())


def enc(arr, codec, q):
    b = io.BytesIO(); im = Image.fromarray(arr)
    if codec == "jpeg":
        im.save(b, "JPEG", quality=q, optimize=True)
    else:
        im.save(b, "WEBP", quality=q, method=6)
    return b.getvalue()


def dec(d):
    return np.asarray(Image.open(io.BytesIO(d)).convert("RGB"))


def bd_saving(ind, atl):
    """Average byte saving of the atlas over individual across the common SSIM range
    (a Bjontegaard-style measure, always defined when the rate-distortion curves overlap).
    Positive = atlas needs fewer bytes at matched quality."""
    si = sorted(ind); sa = sorted(atl)
    xi = [p[0] for p in si]; bi = [math.log(p[1]) for p in si]
    xa = [p[0] for p in sa]; ba = [math.log(p[1]) for p in sa]
    lo, hi = max(min(xi), min(xa)), min(max(xi), max(xa))
    if hi <= lo:
        return None
    xs = np.linspace(lo, hi, 20)
    di = np.interp(xs, xi, bi); da = np.interp(xs, xa, ba)
    bd = 100 * (1 - math.exp(float(np.mean(da - di))))
    # coupling-sensitive: a high-quality point near the top of the common range, where
    # the shared-adaptive-state penalty bites hardest (guards against BD-rate dilution)
    hq_x = lo + 0.85 * (hi - lo)
    hq = 100 * (1 - math.exp(float(np.interp(hq_x, xa, ba) - np.interp(hq_x, xi, bi))))
    return round(bd, 2), round(hq, 2)


def saving(tiles, codec):
    th, tw = tiles[0].shape[:2]; n = len(tiles)
    cols = math.ceil(math.sqrt(n)); rows = math.ceil(n / cols)
    atlas = np.full((rows * th, cols * tw, 3), 255, np.uint8); coords = []
    for i, t in enumerate(tiles):
        r, c = divmod(i, cols); atlas[r * th:(r + 1) * th, c * tw:(c + 1) * tw] = t
        coords.append((r * th, c * tw))
    ind, atl = [], []
    for q in QUALITIES:
        tot, sl = 0, []
        for t in tiles:
            d = enc(t, codec, q); tot += len(d); sl.append(ssim(t, dec(d)))
        ind.append((float(np.mean(sl)), tot))
        d = enc(atlas, codec, q); dd = dec(d)
        sl = [ssim(t, dd[y:y + th, x:x + tw]) for t, (y, x) in zip(tiles, coords)]
        atl.append((float(np.mean(sl)), len(d)))
    ind_bytes = ind[3][1]  # q80 individual total, for the fixed-cost feature
    r = bd_saving(ind, atl)
    return (r, ind_bytes) if r else (None, ind_bytes)


# ---------------- features ----------------

def features(tiles):
    T = np.stack(tiles).astype(np.float32)
    gray = 0.299 * T[..., 0] + 0.587 * T[..., 1] + 0.114 * T[..., 2]
    # edge density (Sobel magnitude)
    gx = np.abs(np.diff(gray, axis=2)).mean(); gy = np.abs(np.diff(gray, axis=1)).mean()
    edge = float((gx + gy) / 2 / 255)
    # DCT/FFT high-frequency energy ratio (per tile, averaged)
    hf = []
    for g in gray:
        F = np.abs(np.fft.fftshift(np.fft.fft2(g))) ** 2
        c = np.array(F.shape) // 2; r = min(F.shape) // 8
        yy, xx = np.ogrid[:F.shape[0], :F.shape[1]]
        low = ((yy - c[0]) ** 2 + (xx - c[1]) ** 2) <= r * r
        hf.append(float(F[~low].sum() / (F.sum() + 1e-9)))
    dct_hf = float(np.mean(hf))
    # color histogram entropy (3 bits/channel)
    q = (T // 32).astype(np.int32)
    idx = (q[..., 0] * 64 + q[..., 1] * 8 + q[..., 2]).ravel()
    h = np.bincount(idx, minlength=512).astype(np.float64); h /= h.sum()
    ent = float(-(h[h > 0] * np.log2(h[h > 0])).sum())
    # mean unique colors per tile
    uniq = float(np.mean([len(np.unique(t.reshape(-1, 3), axis=0)) for t in tiles]))
    # inter-tile heterogeneity (12x12 thumbnails)
    thumb = np.stack([np.asarray(Image.fromarray(t).resize((12, 12), Image.BILINEAR),
                                 np.float32).ravel() / 255 for t in tiles])
    d = np.sqrt(((thumb[:, None] - thumb[None]) ** 2).sum(-1))
    hetero = float(d[np.triu_indices(len(thumb), 1)].mean() / np.sqrt(thumb.shape[1]))
    lum_var = float(np.mean([g.var() for g in gray]) / (255 ** 2))
    return {"edge": edge, "dct_hf": dct_hf, "hist_ent": ent, "uniq": uniq / 1000,
            "hetero": hetero, "lum_var": lum_var}


def build_cells():
    classes = list(NATURAL) + list(SYNTH)
    cells = []
    for cls in classes:
        for size in SIZES:
            tiles = load_tiles(cls, size)
            feat = features(tiles)
            for codec in CODECS:
                sv, ind_bytes = saving(tiles, codec)
                if sv is None:
                    continue
                bd, hq = sv
                # probe-encode: measure the saving on a cheap k-tile pilot (a real
                # measurement, not a source-statistic prediction). Does a tiny probe
                # predict the full-set saving better than the six source features?
                p10 = saving(tiles[:10], codec)[0]
                p20 = saving(tiles[:20], codec)[0]
                cells.append({"cls": cls, "size": size, "codec": codec,
                              "saving": bd, "saving_hq": hq,
                              "probe10": p10[0] if p10 else None,
                              "probe20": p20[0] if p20 else None,
                              "F": 100 * H[codec] * len(tiles) / ind_bytes,
                              "inv_size": 1.0 / size, **feat})
                print(f"  {cls:14} {size:>3} {codec:5} full={bd:+.1f} "
                      f"probe10={p10[0] if p10 else None} probe20={p20[0] if p20 else None}",
                      flush=True)
    json.dump(cells, (OUT / "cells.json").open("w"), indent=1)
    return cells


# ---------------- leave-one-class-out evaluation ----------------

FEATS = ["edge", "dct_hf", "hist_ent", "uniq", "hetero", "lum_var"]


def design(cells, codecs, rich, means, stds):
    cols = [[c["F"] for c in cells], [c["inv_size"] for c in cells]]
    for cc in codecs:
        cols.append([1.0 if c["codec"] == cc else 0.0 for c in cells])
    if rich:
        for i, f in enumerate(FEATS):
            cols.append([(c[f] - means[i]) / stds[i] for c in cells])
    cols.append([1.0] * len(cells))
    return np.array(cols).T


def evaluate_target(cells, target):
    classes = sorted(set(c["cls"] for c in cells))
    codecs = sorted(set(c["codec"] for c in cells))
    res = {"baseline": {"ae": [], "sign": [], "pred": [], "act": []},
           "rich": {"ae": [], "sign": [], "pred": [], "act": []}}
    for held in classes:
        tr = [c for c in cells if c["cls"] != held]
        te = [c for c in cells if c["cls"] == held]
        means = [np.mean([c[f] for c in tr]) for f in FEATS]
        stds = [np.std([c[f] for c in tr]) + 1e-9 for f in FEATS]
        yt = np.array([c[target] for c in te])
        for name, rich in (("baseline", False), ("rich", True)):
            A = design(tr, codecs, rich, means, stds)
            y = np.array([c[target] for c in tr])
            coef, *_ = np.linalg.lstsq(A, y, rcond=None)
            pred = design(te, codecs, rich, means, stds) @ coef
            res[name]["ae"] += np.abs(pred - yt).tolist()
            res[name]["sign"] += (np.sign(pred) == np.sign(yt)).tolist()
            res[name]["pred"] += pred.tolist(); res[name]["act"] += yt.tolist()
    out = {n: {"mae": round(float(np.mean(res[n]["ae"])), 2),
               "sign_acc": round(float(np.mean(res[n]["sign"])), 3),
               "spearman": round(_spearman(res[n]["act"], res[n]["pred"]), 3)} for n in res}
    b, r = out["baseline"], out["rich"]
    out["verdict"] = "RICH WINS" if (r["mae"] < 0.8 * b["mae"] and
                                     r["sign_acc"] > b["sign_acc"]) else "NEGATIVE"
    return out


def _spearman(a, b):
    ra = np.argsort(np.argsort(a)); rb = np.argsort(np.argsort(b))
    return float(np.corrcoef(ra, rb)[0, 1])


def evaluate_probe(cells, probe_key):
    """Leave-one-class-out: predict the full-set BD saving from a cheap probe-encode
    (a real measurement of a k-tile pilot), and directly (probe as the estimate)."""
    cells = [c for c in cells if c.get(probe_key) is not None]
    classes = sorted(set(c["cls"] for c in cells))
    fit_ae, direct_ae = [], []
    for held in classes:
        tr = [c for c in cells if c["cls"] != held]
        te = [c for c in cells if c["cls"] == held]
        X = np.array([[c[probe_key], 1.0] for c in tr]); y = np.array([c["saving"] for c in tr])
        coef, *_ = np.linalg.lstsq(X, y, rcond=None)
        for c in te:
            pred = coef[0] * c[probe_key] + coef[1]
            fit_ae.append(abs(pred - c["saving"]))
            direct_ae.append(abs(c[probe_key] - c["saving"]))
    full = [c["saving"] for c in cells]; prb = [c[probe_key] for c in cells]
    return {"n": len(cells), "mae_fit": round(float(np.mean(fit_ae)), 2),
            "mae_direct": round(float(np.mean(direct_ae)), 2),
            "spearman": round(_spearman(full, prb), 3)}


def evaluate(cells):
    classes = sorted(set(c["cls"] for c in cells))
    summary = {"n_cells": len(cells), "classes": classes, "by_target": {}, "probe": {}}
    for target, label in (("saving", "BD-rate (whole range)"),
                          ("saving_hq", "high-quality point (coupling-sensitive)")):
        s = evaluate_target(cells, target)
        summary["by_target"][target] = s
        b, r = s["baseline"], s["rich"]
        print(f"\n=== leave-one-class-out, target = {label} ===")
        print(f"  baseline (F + 1/size + codec): MAE {b['mae']:.2f}  sign-acc {b['sign_acc']:.3f}")
        print(f"  rich (+ 6 content features):   MAE {r['mae']:.2f}  sign-acc {r['sign_acc']:.3f}")
        print(f"  VERDICT: {s['verdict']} (sign-acc base rate is near-saturated; MAE is the "
              "meaningful metric)")
    # probe-encode: does a cheap measurement beat feature-prediction?
    base_mae = summary["by_target"]["saving"]["baseline"]["mae"]
    rich_mae = summary["by_target"]["saving"]["rich"]["mae"]
    print("\n=== probe-encode vs feature-prediction (target = full BD saving) ===")
    print(f"  feature baseline (F+size+codec) MAE {base_mae:.2f} ; rich features MAE {rich_mae:.2f}")
    for pk in ("probe10", "probe20"):
        p = evaluate_probe(cells, pk)
        summary["probe"][pk] = p
        print(f"  {pk}: fitted-MAE {p['mae_fit']:.2f}  direct-MAE {p['mae_direct']:.2f}  "
              f"Spearman(full,probe) {p['spearman']:.3f}  (n={p['n']})")
    json.dump(summary, (OUT / "results.json").open("w"), indent=1)
    return summary


if __name__ == "__main__":
    import sys
    if "--eval-only" in sys.argv:   # re-score from saved cells.json, no re-encoding
        cells = json.load((OUT / "cells.json").open())
    else:
        cells = build_cells()
    evaluate(cells)
    print("PREDICT DONE")
