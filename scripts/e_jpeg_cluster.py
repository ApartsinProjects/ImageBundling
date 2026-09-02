"""Does clustering tiles by their optimal quantization point (RD-affinity) and coding
each cluster at its own quality beat a single atlas at matched quality?

Mechanism under test: a single atlas must pick ONE quantization operating point, so it
over-codes easy tiles and under-codes hard ones (the shared-adaptive-state penalty, and
the reason the WebP atlas goes negative on heterogeneous photos). If we PARTITION tiles
by the quality q* each needs to reach the target SSIM, and code each cluster at its own
q*, every tile sits near its own best point -- at the cost of k container/table overheads.

We compare four partitions of the SAME tiles, each scored at matched mean SSIM 0.97
(per-cluster quality chosen so each cluster hits the target; bytes summed over clusters):
  single      one atlas, one quality              (the paper's atlas)
  random4     4 random clusters, per-cluster q
  content4    4 k-means-on-thumbnail clusters      (the paper's "cluster-pure" criterion)
  affinity4   4 clusters by q* (this idea)         (common-best-quantization criterion)
plus `individual` (each tile at its own q*), the per-tile lower bound.

Reported: bytes of each scheme relative to `single` (negative = fewer bytes = better)
and relative to `individual`. Codecs jpeg (weak coupling) and webp (strong coupling,
where a win is most likely). Sizes 112, 224 (224 is where the WebP atlas is most negative).

Pre-stated invariants / hypotheses:
  I1 random4 ~ single (a few % worse from k-fold overhead; random clusters share the
     whole-set q* distribution, so per-cluster q barely differs from the single q).
  I2 individual is the byte floor for large photos under WebP (atlas is negative there).
  H  affinity4 < single for WebP at 224 (clusters each fit their quantizer); affinity4
     also < content4 if q*-affinity is a better criterion than visual similarity. For
     JPEG the gap is small (weak coupling). If q* spread across tiles is tiny, no scheme
     can help -- we print the spread so a null is explained, not mysterious.
"""
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image

import e_predict as ep  # enc, dec, ssim, load_tiles

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "results" / "static" / "e_jpeg_cluster"
OUT.mkdir(parents=True, exist_ok=True)

N = 120
SIZES = [112, 224]
CODECS = ["jpeg", "webp"]
LADDER = [50, 65, 80, 90, 95]
TARGET = 0.97
K = 4
RNG = np.random.default_rng(0)


def load_photos(size):
    d = ROOT / "assets" / "photos"
    files = sorted(p for p in d.iterdir()
                   if p.suffix.lower() in (".jpg", ".jpeg", ".png"))[:N]
    out = []
    for f in files:
        im = Image.open(f)
        if im.mode in ("RGBA", "LA", "P"):
            im = Image.alpha_composite(Image.new("RGBA", im.size, (255,) * 4),
                                       im.convert("RGBA"))
        out.append(np.asarray(im.convert("RGB").resize((size, size), Image.LANCZOS)))
    return out


def atlas_of(tiles):
    th, tw = tiles[0].shape[:2]
    n = len(tiles)
    cols = math.ceil(math.sqrt(n)); rows = math.ceil(n / cols)
    a = np.full((rows * th, cols * tw, 3), 255, np.uint8); coords = []
    for i, t in enumerate(tiles):
        r, c = divmod(i, cols)
        a[r * th:(r + 1) * th, c * tw:(c + 1) * tw] = t
        coords.append((r * th, c * tw))
    return a, coords, (th, tw)


def atlas_curve(tiles, codec):
    """(mean per-tile SSIM, bytes) for this tile set as one atlas, over the ladder."""
    a, coords, (th, tw) = atlas_of(tiles)
    curve = []
    for q in LADDER:
        d = ep.enc(a, codec, q); dd = ep.dec(d)
        sl = [ep.ssim(t, dd[y:y + th, x:x + tw]) for t, (y, x) in zip(tiles, coords)]
        curve.append((float(np.mean(sl)), len(d)))
    return curve


def bytes_at_target(curve):
    """Log-linear interpolate bytes at mean SSIM = TARGET (clamped to the curve range)."""
    c = sorted(curve)
    xs = [s for s, _ in c]; ys = [math.log(b) for _, b in c]
    return math.exp(float(np.interp(TARGET, xs, ys)))


def partition_bytes(clusters, codec):
    """Total matched-SSIM bytes = sum over clusters of (cluster atlas bytes at its own
    quality that hits TARGET). Each cluster hits the target, so the overall mean does too."""
    return sum(bytes_at_target(atlas_curve(c, codec)) for c in clusters)


def tile_qstar(tile, codec):
    ss = [ep.ssim(tile, ep.dec(ep.enc(tile, codec, q))) for q in LADDER]
    return float(np.interp(TARGET, ss, LADDER))


def individual_bytes(tiles, codec, qstar):
    """Each tile coded at the quality that puts it at TARGET (per-tile optimum)."""
    tot = 0.0
    for t, q in zip(tiles, qstar):
        qi = int(round(min(max(q, LADDER[0]), LADDER[-1])))
        tot += len(ep.enc(t, codec, qi))
    return tot


def kmeans_thumbs(tiles, k, iters=15):
    X = np.stack([np.asarray(Image.fromarray(t).resize((12, 12), Image.BILINEAR),
                             np.float32).ravel() for t in tiles])
    idx = RNG.choice(len(X), k, replace=False)
    cent = X[idx].copy()
    lab = np.zeros(len(X), int)
    for _ in range(iters):
        d = ((X[:, None] - cent[None]) ** 2).sum(-1)
        lab = d.argmin(1)
        for j in range(k):
            if (lab == j).any():
                cent[j] = X[lab == j].mean(0)
    return lab


def split_by(labels, tiles, k):
    return [[t for t, l in zip(tiles, labels) if l == j] for j in range(k)
            if any(l == j for l in labels)]


def main():
    rows = []
    invariants = []
    for size in SIZES:
        tiles = load_photos(size)
        for codec in CODECS:
            qstar = [tile_qstar(t, codec) for t in tiles]
            qs = np.array(qstar)
            spread = f"q* mean={qs.mean():.1f} sd={qs.std():.1f} [{qs.min():.0f},{qs.max():.0f}]"

            single = partition_bytes([tiles], codec)

            ridx = RNG.permutation(len(tiles))
            rand = [ [tiles[i] for i in ridx[j::K]] for j in range(K) ]

            content = split_by(kmeans_thumbs(tiles, K), tiles, K)

            order = np.argsort(qs)
            aff = [ [tiles[i] for i in order[j * len(tiles) // K:(j + 1) * len(tiles) // K]]
                    for j in range(K) ]

            b_rand = partition_bytes(rand, codec)
            b_content = partition_bytes(content, codec)
            b_aff = partition_bytes(aff, codec)
            b_ind = individual_bytes(tiles, codec, qstar)

            def rel(x, base):
                return round(100 * (x / base - 1), 2)  # % vs base (neg = fewer bytes)

            row = {
                "size": size, "codec": codec, "qstar_spread": spread,
                "single_bytes": int(single), "individual_bytes": int(b_ind),
                "random4_vs_single": rel(b_rand, single),
                "content4_vs_single": rel(b_content, single),
                "affinity4_vs_single": rel(b_aff, single),
                "affinity4_vs_content4": rel(b_aff, b_content),
                "single_vs_individual": rel(single, b_ind),
                "affinity4_vs_individual": rel(b_aff, b_ind),
            }
            rows.append(row)
            print(f"[{codec:5} {size:>3}] {spread}")
            print(f"    vs single:  random4 {row['random4_vs_single']:+}%  "
                  f"content4 {row['content4_vs_single']:+}%  affinity4 {row['affinity4_vs_single']:+}%")
            print(f"    vs individ: single {row['single_vs_individual']:+}%  "
                  f"affinity4 {row['affinity4_vs_individual']:+}%   "
                  f"(affinity4 vs content4 {row['affinity4_vs_content4']:+}%)", flush=True)

    # I1: random4 within a few % of single
    for r in rows:
        invariants.append(("I1 random4~single (<6% worse)", r["codec"], r["size"],
                           abs(r["random4_vs_single"]) < 6, r["random4_vs_single"]))
    print("\n=== invariants ===")
    for n, c, s, ok, g in invariants:
        print(f"  {'PASS' if ok else 'FAIL'} {n} [{c} {s}] got={g}")

    json.dump({"rows": rows}, (OUT / "results.json").open("w"), indent=1)
    print("\nCLUSTER DONE")


if __name__ == "__main__":
    main()
