"""Smoke test: shared coarse base + per-tile residual (the client-side "coarse+fine"
atlas). For a cluster, encode ONE shared base (cluster mean) plus a signed residual per
tile; reconstruct base + (residual-128) as a WebGL shader would. Does base + N residuals
beat N independent tiles at matched reconstruction SSIM?

This attacks the cross-image PIXEL redundancy a plain lossy atlas cannot share. Prior
(honest): residuals of dissimilar tiles are high-entropy and JPEG codes them poorly, plus
the base is extra overhead -> expected to LOSE on generic clusters and WIN only when tiles
are near-duplicates (variant/recolored images). We delineate exactly where the line is.

Regimes:
  A generic   content-clustered ImageNet tiles (real but not duplicates)
  B near-dup  groups = one base tile + M variants (brightness/noise/shift/recolor)
  INV identical copies of one tile -> residuals ~0 -> must save a lot (sanity invariant)

Metric per group: total bytes (base + residuals) vs independent tiles, each at matched
reconstruction SSIM 0.97. saving = 1 - resid_scheme/independent (positive = fewer bytes).
JPEG.
"""
import io
import json
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import e_predict as ep
import e_jpeg_cluster as ec
import e_pivot_validate as pv

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "results" / "static" / "e_residual"
OUT.mkdir(parents=True, exist_ok=True)

SIZE = 128
TARGET = 0.97
QR = [40, 55, 70, 82, 90, 95]
QB = 92                    # shared-base quality (kept high; amortized over the cluster)
RNG = np.random.default_rng(2)


def jbytes(arr, q):
    b = io.BytesIO(); Image.fromarray(arr).save(b, "JPEG", quality=q, optimize=True)
    return b.getvalue()


def jdec(d):
    return np.asarray(Image.open(io.BytesIO(d)).convert("RGB")).astype(np.float64)


def interp_at(pts):
    pts = sorted(pts)
    xs = [s for s, _ in pts]; ys = [math.log(b) for _, b in pts]
    return math.exp(float(np.interp(TARGET, xs, ys))), (TARGET < xs[0] or TARGET > xs[-1])


def independent_bytes(cluster):
    tot, clamp = 0.0, False
    for t in cluster:
        pts = []
        for q in QR:
            d = jbytes(t, q); pts.append((ep.ssim(t, jdec(d).astype(np.uint8)), len(d)))
        b, cl = interp_at(pts); tot += b; clamp = clamp or cl
    return tot, clamp


def residual_bytes(cluster):
    base = np.clip(np.mean(np.stack(cluster).astype(np.float64), 0), 0, 255).astype(np.uint8)
    bd = jbytes(base, QB)
    Bdec = jdec(bd)
    tot = float(len(bd)); clamp = False
    for t in cluster:
        resid = t.astype(np.float64) - Bdec
        off = np.clip(resid + 128, 0, 255).astype(np.uint8)
        pts = []
        for q in QR:
            d = jbytes(off, q); Rdec = jdec(d)
            recon = np.clip(Bdec + (Rdec - 128), 0, 255).astype(np.uint8)
            pts.append((ep.ssim(t, recon), len(d)))
        b, cl = interp_at(pts); tot += b; clamp = clamp or cl
    return tot, clamp


def saving(cluster):
    ind, c1 = independent_bytes(cluster)
    res, c2 = residual_bytes(cluster)
    return round(100 * (1 - res / ind), 2), (c1 or c2)


def make_variants(base, m):
    out = [base]
    for _ in range(m - 1):
        v = base.astype(np.float64)
        v = v + RNG.normal(0, 4, v.shape)                       # mild noise
        v = v * RNG.uniform(0.93, 1.07)                         # brightness
        v[..., RNG.integers(0, 3)] *= RNG.uniform(0.9, 1.1)     # slight recolor
        sh = RNG.integers(-2, 3, 2)                             # small shift
        v = np.roll(np.roll(v, sh[0], 0), sh[1], 1)
        out.append(np.clip(v, 0, 255).astype(np.uint8))
    return out


def main():
    pool = pv.build_pool(SIZE)
    print(f"pool {len(pool)} @ {SIZE}px")

    # INV: identical copies
    inv_cluster = [pool[0].copy() for _ in range(12)]
    inv_save, _ = saving(inv_cluster)

    # A generic: content-cluster a diverse draw into k=8, saving per cluster
    idx = RNG.choice(len(pool), 160, replace=False)
    tiles = [pool[i] for i in idx]
    lab = ec.kmeans_thumbs(tiles, 8)
    gen = [c for c in ec.split_by(lab, tiles, 8) if len(c) >= 4]
    gen_sav = [saving(c)[0] for c in gen]

    # B near-dup: 6 groups, each base + 9 variants
    nd_sav = []
    for _ in range(6):
        base = pool[RNG.integers(0, len(pool))]
        nd_sav.append(saving(make_variants(base, 10))[0])

    summary = {
        "invariant_identical_copies_saving_pct": inv_save,
        "generic_clusters": {"n": len(gen_sav),
                             "mean": round(float(np.mean(gen_sav)), 2),
                             "min": round(float(np.min(gen_sav)), 2),
                             "max": round(float(np.max(gen_sav)), 2),
                             "per_cluster": [round(x, 1) for x in gen_sav]},
        "near_duplicate_groups": {"n": len(nd_sav),
                                  "mean": round(float(np.mean(nd_sav)), 2),
                                  "min": round(float(np.min(nd_sav)), 2),
                                  "max": round(float(np.max(nd_sav)), 2),
                                  "per_group": [round(x, 1) for x in nd_sav]},
    }
    json.dump(summary, (OUT / "results.json").open("w"), indent=1)

    print("\n=== shared-base + residual vs independent (JPEG, matched recon SSIM 0.97) ===")
    print(f"  INVARIANT identical copies:   {inv_save:+.1f}%  (must be strongly positive)")
    print(f"  A generic ImageNet clusters:  mean {summary['generic_clusters']['mean']:+.1f}%  "
          f"[{summary['generic_clusters']['min']:+.1f}, {summary['generic_clusters']['max']:+.1f}]")
    print(f"  B near-duplicate groups:      mean {summary['near_duplicate_groups']['mean']:+.1f}%  "
          f"[{summary['near_duplicate_groups']['min']:+.1f}, {summary['near_duplicate_groups']['max']:+.1f}]")
    print("  (positive = residual scheme uses FEWER bytes than independent tiles)")
    print("RESIDUAL DONE")


if __name__ == "__main__":
    main()
