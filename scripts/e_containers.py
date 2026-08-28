"""Test two container tricks that keep per-tile encoding (Fable ideas 1.1 and 1.4).

SHARED-TABLES JPEG (abbreviated format): tiles encoded with identical (fixed) tables
share one DQT+DHT+frame+scan-header prefix; the bundle stores that prefix once plus
each tile's entropy-coded remainder. Scans are byte-identical to the per-tile
fixed-table JPEG, so quality is exactly equal by construction. Compared against
per-tile optimized JPEG (the individual-serving optimum), the fixed-table per-tile
sum, and the JPEG grid atlas.

ANIMATED WEBP container: one tile per ANMF frame; each frame is an independent VP8
payload with its own entropy tables and 4 quantizer segments, inside one file/one
request. Frames encoded at the same quality as the individual tiles, so quality is
equal. Compared against per-tile WebP and the WebP grid atlas.

Both measured on emoji (72px flat art) and photos (224 and 112px, deduplicated).
Bytes only; decode-path support (ImageDecoder; Safari fallback) is noted, not tested.
"""
import io
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image

import static_study as ss

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "results" / "static" / "e_containers"
OUT.mkdir(parents=True, exist_ok=True)


def dedup(tiles):
    import hashlib
    seen, uniq = set(), []
    for t in tiles:
        k = hashlib.md5(t.tobytes()).hexdigest()
        if k not in seen:
            seen.add(k)
            uniq.append(t)
    return uniq


def jpeg(t, q, optimize):
    b = io.BytesIO()
    Image.fromarray(t).save(b, "JPEG", quality=q, optimize=optimize)
    return b.getvalue()


def common_prefix_len(blobs):
    """Length of the byte-identical shared head across all blobs."""
    ref = blobs[0]
    lo, hi = 0, len(ref)
    for b in blobs:
        m = min(hi, len(b))
        i = 0
        while i < m and b[i] == ref[i]:
            i += 1
        hi = i
    return hi


def shared_tables_bundle(tiles, q):
    """Bundle size = one shared prefix + each tile's non-shared remainder + tiny index.
    Uses fixed (non-optimized) tables so the prefix is identical across tiles."""
    blobs = [jpeg(t, q, optimize=False) for t in tiles]
    pref = common_prefix_len(blobs)
    remainders = sum(len(b) - pref for b in blobs)
    index = 4 * len(blobs)  # 4 bytes offset per tile
    return pref + remainders + index, pref, sum(len(b) for b in blobs)


def anim_webp(tiles, q, lossless=False):
    frames = [Image.fromarray(t) for t in tiles]
    b = io.BytesIO()
    frames[0].save(b, "WEBP", save_all=True, append_images=frames[1:],
                   quality=q, method=4, lossless=lossless, duration=100)
    return len(b.getvalue())


def webp(t, q, lossless=False):
    b = io.BytesIO()
    Image.fromarray(t).save(b, "WEBP", quality=q, method=4, lossless=lossless)
    return b.getvalue()


def grid_atlas_bytes(tiles, save_fn):
    n = len(tiles)
    th, tw, _ = tiles[0].shape
    cols = math.ceil(math.sqrt(n))
    rows = math.ceil(n / cols)
    atlas = np.full((rows * th, cols * tw, 3), 255, np.uint8)
    for i, t in enumerate(tiles):
        r, c = divmod(i, cols)
        atlas[r * th:(r + 1) * th, c * tw:(c + 1) * tw] = t
    return len(save_fn(atlas))


def main():
    rows = []

    def emit(**kw):
        rows.append(kw)
        print(kw, flush=True)

    classes = [("emoji", None), ("photos", None), ("photos112", None)]
    for cls, _ in classes:
        tiles, _ = ss.load_tiles(cls, 500)
        if cls.startswith("photos"):
            tiles = dedup(tiles)
        n = len(tiles)
        for q in (50, 80):
            # --- JPEG family
            ind_opt = sum(len(jpeg(t, q, True)) for t in tiles)
            ind_fixed = sum(len(jpeg(t, q, False)) for t in tiles)
            atlas_j = grid_atlas_bytes(tiles, lambda a: jpeg(a, q, True))
            shared, pref, _ = shared_tables_bundle(tiles, q)
            emit(cls=cls, n=n, q=q, codec="jpeg", cond="individual_optimized", bytes=ind_opt)
            emit(cls=cls, n=n, q=q, codec="jpeg", cond="individual_fixed", bytes=ind_fixed)
            emit(cls=cls, n=n, q=q, codec="jpeg", cond="grid_atlas", bytes=atlas_j)
            emit(cls=cls, n=n, q=q, codec="jpeg", cond="shared_tables_bundle",
                 bytes=shared, prefix=pref,
                 save_vs_ind_opt=round(100 * (1 - shared / ind_opt), 1),
                 save_vs_atlas=round(100 * (1 - shared / atlas_j), 1))
            # --- WebP family
            ind_w = sum(len(webp(t, q)) for t in tiles)
            atlas_w = grid_atlas_bytes(tiles, lambda a: webp(a, q))
            anim = anim_webp(tiles, q)
            emit(cls=cls, n=n, q=q, codec="webp", cond="individual", bytes=ind_w)
            emit(cls=cls, n=n, q=q, codec="webp", cond="grid_atlas", bytes=atlas_w)
            emit(cls=cls, n=n, q=q, codec="webp", cond="animated_webp", bytes=anim,
                 save_vs_ind=round(100 * (1 - anim / ind_w), 1),
                 save_vs_atlas=round(100 * (1 - anim / atlas_w), 1))

    json.dump(rows, (OUT / "results.json").open("w"), indent=1)
    (OUT / "results.jsonl").write_text("\n".join(json.dumps(r) for r in rows))
    print("CONTAINERS DONE")


if __name__ == "__main__":
    main()
