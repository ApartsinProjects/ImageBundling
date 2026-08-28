"""E3.7: layout variants for atlas packing.

A. Vertical strip (1 tile per row band): restores PNG's per-scanline filter locality.
   PNG only for tall strips (WebP max dimension 16383 limits it to small N).
B. Block-aligned cells: pad 72px tiles to 80px cells (edge-replicate 4px) so 16px DCT
   blocks never straddle tiles; compare pad 0 (misaligned) / 4 (aligned) / 8
   (misaligned, bigger) at matched SSIM for jpeg/webp.
C. Serpentine cluster placement: kmeans-sorted order laid out boustrophedon so row
   ends keep similar neighbors adjacent in 2D (vs row-major).

Usage: python e37_layouts.py --tag e37 [--n 500]
"""
import argparse
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image

import static_study as ss
from e31_ordering import kmeans, thumbs

ROOT = Path(__file__).resolve().parent.parent


def enc_bytes(arr, codec, q):
    return len(ss.encode(Image.fromarray(arr), codec, q))


def grid(tiles, serpentine=False):
    n = len(tiles)
    th, tw, _ = tiles[0].shape
    cols = math.ceil(math.sqrt(n))
    rows = math.ceil(n / cols)
    atlas = np.full((rows * th, cols * tw, 3), 255, np.uint8)
    for i, t in enumerate(tiles):
        r, c = divmod(i, cols)
        if serpentine and r % 2 == 1:
            c = cols - 1 - c
        atlas[r * th:(r + 1) * th, c * tw:(c + 1) * tw] = t
    return atlas


def strip(tiles):
    return np.concatenate(tiles, axis=0)


def aligned_grid(tiles, pad):
    """Edge-replicated pad on all sides -> cell = tile + 2*pad."""
    a, _ = ss.build_atlas(tiles, pad)
    return a


def matched_bytes(tiles, build, codec, qlo=50, qhi=80, target=0.97):
    """2-point log interpolation of bytes at SSIM target for a layout builder."""
    pts = []
    for q in (qlo, qhi):
        atlas = build()
        blob = ss.encode(Image.fromarray(atlas), codec, q)
        # ssim measured on the plain grid crop is layout-specific; for the alignment
        # test we crop back from the padded grid
        pts.append((q, len(blob)))
    return pts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="e37")
    ap.add_argument("--n", type=int, default=500)
    args = ap.parse_args()
    outdir = ROOT / "results" / "static" / args.tag
    outdir.mkdir(parents=True, exist_ok=True)
    out = (outdir / "results.jsonl").open("a")
    R = []

    def emit(**kw):
        R.append(kw)
        out.write(json.dumps(kw) + "\n")
        out.flush()
        print(kw, flush=True)

    for cls in ("emoji", "photos"):
        tiles, _ = ss.load_tiles(cls, args.n)
        # dedup photos so results are not duplicate-driven
        if cls == "photos":
            import hashlib
            seen, uniq = set(), []
            for t in tiles:
                k = hashlib.md5(t.tobytes()).hexdigest()
                if k not in seen:
                    seen.add(k)
                    uniq.append(t)
            tiles = uniq
        n = len(tiles)
        lab = kmeans(thumbs(tiles), max(2, math.ceil(math.sqrt(n))))
        luma = thumbs(tiles).reshape(n, -1, 3).mean((1, 2))
        korder = sorted(range(n), key=lambda i: (lab[i], luma[i]))
        ktiles = [tiles[i] for i in korder]

        # --- A: strip vs grid vs individual (lossless)
        for codec in ("png",):
            ind = sum(enc_bytes(t, codec, None) for t in tiles)
            emit(cls=cls, n=n, exp="A_strip", codec=codec, cond="individual", bytes=ind)
            emit(cls=cls, n=n, exp="A_strip", codec=codec, cond="grid",
                 bytes=enc_bytes(grid(tiles), codec, None))
            emit(cls=cls, n=n, exp="A_strip", codec=codec, cond="strip",
                 bytes=enc_bytes(strip(tiles), codec, None))
            emit(cls=cls, n=n, exp="A_strip", codec=codec, cond="strip_kmeans",
                 bytes=enc_bytes(strip(ktiles), codec, None))

        # --- C: serpentine cluster placement (lossless + lossy webp)
        for codec, q in (("png", None), ("webp_ll", None), ("webp", 80)):
            if codec == "webp_ll" and cls == "photos":
                pass  # runs, just slow
            emit(cls=cls, n=n, exp="C_serp", codec=codec, q=q, cond="rowmajor_kmeans",
                 bytes=enc_bytes(grid(ktiles), codec, q))
            emit(cls=cls, n=n, exp="C_serp", codec=codec, q=q, cond="serpentine_kmeans",
                 bytes=enc_bytes(grid(ktiles, serpentine=True), codec, q))

    # --- B: block alignment (emoji 72px only; 224 is already 16-aligned)
    tiles, _ = ss.load_tiles("emoji", args.n)
    for codec in ("jpeg", "webp"):
        for pad in (0, 4, 8):
            for q in (50, 80):
                atlas, coords = ss.build_atlas(tiles, pad)
                blob = ss.encode(Image.fromarray(atlas), codec, q)
                got = ss.crop_tiles(ss.decode(blob), coords, 72, 72)
                sims = np.array([ss.ssim(t, g) for t, g in zip(tiles, got)])
                emit(cls="emoji", n=args.n, exp="B_align", codec=codec, q=q, pad=pad,
                     cell=72 + 2 * pad, bytes=len(blob),
                     ssim=round(float(sims.mean()), 5))
    print("E37 DONE")


if __name__ == "__main__":
    main()
