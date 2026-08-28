"""E3.1: does grouping visually similar tiles reduce atlas bytes?

The same tiles are packed in different ORDERS (adjacency patterns) and, for the
chunked case, different PARTITIONS; bytes at fixed encoder settings and per-tile SSIM
are measured for each. Orderings:
  baseline  : sorted filename order (what Phase 1 used)
  random_s  : shuffled, seeds 0/1/2
  luma      : sorted by mean luminance
  meancolor : sorted by mean (R,G,B) lexicographically
  kmeans    : k-means (k=grid columns) on 12x12 thumbnails, clusters laid out
              contiguously, members sorted by luma within cluster
  greedy_nn : greedy nearest-neighbor chain on 12x12-thumbnail L2 distance

Partition conditions (chunks=4): random split vs kmeans(4) cluster split.

Usage: python e31_ordering.py --tag e31 --classes emoji,photos --n 500 \
       --codecs avif:50,avif:80,webp:80,jpeg:80,png,webp_ll [--orders ...]
"""
import argparse
import json
import math
import random
import time
from pathlib import Path

import numpy as np

import static_study as ss

ROOT = Path(__file__).resolve().parent.parent


def thumbs(tiles, size=12):
    from PIL import Image
    return np.stack([
        np.asarray(Image.fromarray(t).resize((size, size), Image.BILINEAR),
                   dtype=np.float32).ravel() for t in tiles])


def kmeans(X, k, iters=25, seed=0):
    rng = np.random.default_rng(seed)
    C = X[rng.choice(len(X), k, replace=False)].copy()
    lab = np.zeros(len(X), int)
    for _ in range(iters):
        d = ((X[:, None, :] - C[None]) ** 2).sum(-1)
        new = d.argmin(1)
        if (new == lab).all():
            break
        lab = new
        for j in range(k):
            if (lab == j).any():
                C[j] = X[lab == j].mean(0)
    return lab


def orderings(tiles, which):
    n = len(tiles)
    T = thumbs(tiles)
    luma = T.reshape(n, -1, 3) @ np.array([0.299, 0.587, 0.114], dtype=np.float32)
    luma = luma.mean(1)
    out = {}
    if "baseline" in which:
        out["baseline"] = list(range(n))
    for s in (0, 1, 2):
        key = f"random_{s}"
        if key in which:
            idx = list(range(n))
            random.Random(s).shuffle(idx)
            out[key] = idx
    if "luma" in which:
        out["luma"] = list(np.argsort(luma))
    if "meancolor" in which:
        mc = T.reshape(n, -1, 3).mean(1)
        out["meancolor"] = sorted(range(n), key=lambda i: tuple(mc[i]))
    if "kmeans" in which:
        k = max(2, math.ceil(math.sqrt(n)))
        lab = kmeans(T, k)
        out["kmeans"] = sorted(range(n), key=lambda i: (lab[i], luma[i]))
    if "greedy_nn" in which:
        left = set(range(n))
        cur = int(np.argmin(luma))
        order = [cur]
        left.remove(cur)
        while left:
            rest = np.array(sorted(left))
            d = ((T[rest] - T[cur]) ** 2).sum(1)
            cur = int(rest[d.argmin()])
            order.append(cur)
            left.remove(cur)
        out["greedy_nn"] = order
    return out


def measure_atlas(tiles, codec, q):
    from PIL import Image
    atlas, coords = ss.build_atlas(tiles, 0)
    t0 = time.perf_counter()
    blob = ss.encode(Image.fromarray(atlas), codec, q)
    enc_s = time.perf_counter() - t0
    th, tw, _ = tiles[0].shape
    got = ss.crop_tiles(ss.decode(blob), coords, th, tw)
    sims = np.array([ss.ssim(t, g) for t, g in zip(tiles, got)])
    return len(blob), float(sims.mean()), float(sims.min()), round(enc_s, 2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--classes", default="emoji,photos")
    ap.add_argument("--n", type=int, default=500)
    ap.add_argument("--codecs", default="avif:50,avif:80,webp:80,jpeg:80,png,webp_ll")
    ap.add_argument("--orders", default="baseline,random_0,random_1,random_2,luma,"
                                        "meancolor,kmeans,greedy_nn")
    ap.add_argument("--chunks", type=int, default=4)
    args = ap.parse_args()

    outdir = ROOT / "results" / "static" / args.tag
    outdir.mkdir(parents=True, exist_ok=True)
    out = (outdir / "results.jsonl").open("a")
    which = args.orders.split(",")

    for cls in args.classes.split(","):
        tiles, _ = ss.load_tiles(cls, args.n)
        orders = orderings(tiles, which)
        for codec, q in (ss.parse_codec(s) for s in args.codecs.split(",")):
            for oname, idx in orders.items():
                ordered = [tiles[i] for i in idx]
                b, sm, smin, enc_s = measure_atlas(ordered, codec, q)
                row = {"cls": cls, "n": args.n, "codec": codec, "q": q,
                       "order": oname, "chunks": 1, "bytes": b,
                       "ssim_mean": round(sm, 5), "ssim_min": round(smin, 5),
                       "enc_s": enc_s}
                out.write(json.dumps(row) + "\n")
                out.flush()
                print(row, flush=True)
            # chunked partitions: random vs kmeans clusters
            k = args.chunks
            parts = {}
            idx = list(range(len(tiles)))
            random.Random(0).shuffle(idx)
            per = math.ceil(len(tiles) / k)
            parts["chunk_random"] = [idx[i * per:(i + 1) * per] for i in range(k)]
            lab = kmeans(thumbs(tiles), k)
            parts["chunk_kmeans"] = [[i for i in range(len(tiles)) if lab[i] == j]
                                     for j in range(k)]
            for pname, groups in parts.items():
                tot, sims = 0, []
                for g in groups:
                    if not g:
                        continue
                    b, sm, smin, _ = measure_atlas([tiles[i] for i in g], codec, q)
                    tot += b
                    sims.append(sm)
                row = {"cls": cls, "n": args.n, "codec": codec, "q": q,
                       "order": pname, "chunks": k, "bytes": tot,
                       "ssim_mean": round(float(np.mean(sims)), 5)}
                out.write(json.dumps(row) + "\n")
                out.flush()
                print(row, flush=True)


if __name__ == "__main__":
    main()
