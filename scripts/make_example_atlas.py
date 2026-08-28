"""Generate example atlas figures + their stats for the results page.

Writes docs/img/atlas_<cls>_<n>.<ext> (display copy) and docs/img/examples.json with
measured per-example stats (individual vs atlas bytes for two representative codecs).
"""
import io
import json
import math
from pathlib import Path

import numpy as np
import pillow_jxl  # noqa: F401
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "img"
OUT.mkdir(parents=True, exist_ok=True)


def load_tiles(cls, n):
    tiles = []
    for f in sorted((ROOT / "assets" / cls).iterdir())[:n]:
        im = Image.open(f)
        if im.mode in ("RGBA", "LA", "P"):
            im = im.convert("RGBA")
            im = Image.alpha_composite(Image.new("RGBA", im.size, (255,) * 4), im)
        tiles.append(np.asarray(im.convert("RGB")))
    return tiles


def build_atlas(tiles):
    n = len(tiles)
    th, tw, _ = tiles[0].shape
    cols = math.ceil(math.sqrt(n))
    rows = math.ceil(n / cols)
    atlas = np.full((rows * th, cols * tw, 3), 255, np.uint8)
    for i, t in enumerate(tiles):
        r, c = divmod(i, cols)
        atlas[r * th:(r + 1) * th, c * tw:(c + 1) * tw] = t
    return atlas


def enc(img, codec, **kw):
    b = io.BytesIO()
    img.save(b, codec, **kw)
    return len(b.getvalue())


def measure(tiles, atlas, codec, **kw):
    ind = sum(enc(Image.fromarray(t), codec, **kw) for t in tiles)
    atl = enc(Image.fromarray(atlas), codec, **kw)
    return ind, atl


examples = []
for cls, n, disp_codec, disp_kw, ext in [
        ("emoji", 100, "PNG", {}, "png"),
        ("photos", 25, "JPEG", {"quality": 85}, "jpg")]:
    tiles = load_tiles(cls, n)
    atlas = build_atlas(tiles)
    name = f"atlas_{cls}_{n}.{ext}"
    Image.fromarray(atlas).save(OUT / name, disp_codec, **disp_kw)
    stats = {}
    for label, codec, kw in [("AVIF q50", "AVIF", {"quality": 50}),
                             ("WebP q80", "WEBP", {"quality": 80, "method": 6}),
                             ("JPEG q80", "JPEG", {"quality": 80, "optimize": True})]:
        ind, atl = measure(tiles, atlas, codec, **kw)
        stats[label] = {"individual": ind, "atlas": atl,
                        "saving_pct": round(100 * (1 - atl / ind), 1)}
    examples.append({"class": cls, "n": n, "file": name,
                     "grid": f"{math.ceil(math.sqrt(n))}x{math.ceil(n/math.ceil(math.sqrt(n)))}",
                     "tile": f"{tiles[0].shape[1]}x{tiles[0].shape[0]}",
                     "atlas_px": f"{atlas.shape[1]}x{atlas.shape[0]}", "stats": stats})
    print(cls, n, stats)

json.dump(examples, (OUT / "examples.json").open("w"), indent=1)
print("wrote", OUT / "examples.json")
