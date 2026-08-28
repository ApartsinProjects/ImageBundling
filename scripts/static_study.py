"""Phase 1 static compression study: atlas vs individual encoding, no network.

For each (class, N, codec, quality, packing) condition, encode the same tiles
(a) as N individual files and (b) as one grid atlas, then measure total bytes,
per-tile SSIM (computed after cropping the tile back out of the decoded result,
so atlas border bleed is captured), and encode/decode wall time.

Alpha handling: all tiles are composited over white to RGB at load time, so every
codec sees identical pixels (JPEG has no alpha; this keeps the comparison fair).

Usage:
  python static_study.py --tag smoke1 --classes emoji --counts 8 --codecs png,webp:80 --paddings 0,8
  python static_study.py --tag run1  # full default sweep
"""
import argparse
import io
import json
import math
import time
from pathlib import Path

import numpy as np
from PIL import Image

try:
    import pillow_jxl  # noqa: F401  (registers JXL with Pillow)
    HAVE_JXL = True
except ImportError:
    HAVE_JXL = False

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"

# ---------------------------------------------------------------- SSIM (luma, 8x8 box window)

def _box(x, w):
    """Box-filter mean via cumulative sums, 'valid' region."""
    c = np.cumsum(np.cumsum(x, axis=0), axis=1)
    c = np.pad(c, ((1, 0), (1, 0)))
    return (c[w:, w:] - c[:-w, w:] - c[w:, :-w] + c[:-w, :-w]) / (w * w)


def ssim(a, b, window=8):
    """SSIM on luma of two uint8 RGB arrays of equal shape."""
    ya = (0.299 * a[..., 0] + 0.587 * a[..., 1] + 0.114 * a[..., 2]).astype(np.float64)
    yb = (0.299 * b[..., 0] + 0.587 * b[..., 1] + 0.114 * b[..., 2]).astype(np.float64)
    w = min(window, ya.shape[0], ya.shape[1])
    C1, C2 = (0.01 * 255) ** 2, (0.03 * 255) ** 2
    ma, mb = _box(ya, w), _box(yb, w)
    vaa = _box(ya * ya, w) - ma * ma
    vbb = _box(yb * yb, w) - mb * mb
    vab = _box(ya * yb, w) - ma * mb
    s = ((2 * ma * mb + C1) * (2 * vab + C2)) / ((ma * ma + mb * mb + C1) * (vaa + vbb + C2))
    return float(s.mean())

# ---------------------------------------------------------------- codecs

def parse_codec(spec):
    """'png' -> ('png', None); 'webp:80' -> ('webp', 80)."""
    if ":" in spec:
        name, q = spec.split(":")
        return name, int(q)
    return spec, None


def encode(img, codec, quality):
    """Encode a PIL RGB image; return bytes."""
    buf = io.BytesIO()
    if codec == "png":
        img.save(buf, "PNG", optimize=True)
    elif codec == "webp_ll":
        img.save(buf, "WEBP", lossless=True, quality=100, method=6)
    elif codec == "webp":
        img.save(buf, "WEBP", quality=quality, method=6)
    elif codec == "jpeg":
        img.save(buf, "JPEG", quality=quality, optimize=True)
    elif codec == "avif":
        img.save(buf, "AVIF", quality=quality)
    elif codec == "jxl":
        img.save(buf, "JXL", quality=quality)
    elif codec == "jxl_ll":
        img.save(buf, "JXL", lossless=True)
    else:
        raise ValueError(f"unknown codec {codec}")
    return buf.getvalue()


def decode(data):
    return np.asarray(Image.open(io.BytesIO(data)).convert("RGB"))

# ---------------------------------------------------------------- assets

def load_tiles(cls, n):
    """Class name may carry a resize suffix: 'photos112' loads 'photos' at 112x112."""
    import re
    m = re.fullmatch(r"([a-z]+?)(\d+)", cls)
    resize = int(m.group(2)) if m and not (ASSETS / cls).exists() else None
    d = ASSETS / (m.group(1) if resize else cls)
    files = sorted(d.iterdir())[:n]
    if len(files) < n:
        raise SystemExit(f"only {len(files)} assets in {d}, need {n}")
    tiles = []
    for f in files:
        im = Image.open(f)
        if im.mode in ("RGBA", "LA", "P"):
            im = im.convert("RGBA")
            bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
            im = Image.alpha_composite(bg, im)
        im = im.convert("RGB")
        if resize:
            im = im.resize((resize, resize), Image.LANCZOS)
        tiles.append(np.asarray(im))
    shapes = {t.shape for t in tiles}
    if len(shapes) != 1:
        raise SystemExit(f"mixed tile shapes in {cls}: {shapes}")
    return tiles, [f.name for f in files]

# ---------------------------------------------------------------- atlas

def build_atlas(tiles, pad):
    """Grid atlas; each tile edge-replicated by `pad` px on all sides."""
    n = len(tiles)
    th, tw, _ = tiles[0].shape
    cols = math.ceil(math.sqrt(n))
    rows = math.ceil(n / cols)
    ch, cw = th + 2 * pad, tw + 2 * pad
    atlas = np.full((rows * ch, cols * cw, 3), 255, dtype=np.uint8)
    coords = []
    for i, t in enumerate(tiles):
        r, c = divmod(i, cols)
        padded = np.pad(t, ((pad, pad), (pad, pad), (0, 0)), mode="edge")
        atlas[r * ch:(r + 1) * ch, c * cw:(c + 1) * cw] = padded
        coords.append((r * ch + pad, c * cw + pad))
    return atlas, coords


def crop_tiles(decoded, coords, th, tw):
    return [decoded[y:y + th, x:x + tw] for (y, x) in coords]

# ---------------------------------------------------------------- study

def run_condition(tiles, codec, quality, mode, pad):
    th, tw, _ = tiles[0].shape
    if mode == "individual":
        total, ssims = 0, []
        t0 = time.perf_counter()
        blobs = [encode(Image.fromarray(t), codec, quality) for t in tiles]
        t_enc = time.perf_counter() - t0
        t0 = time.perf_counter()
        for t, b in zip(tiles, blobs):
            total += len(b)
            ssims.append(ssim(t, decode(b)))
        t_dec = time.perf_counter() - t0
    else:
        atlas, coords = build_atlas(tiles, pad)
        t0 = time.perf_counter()
        blob = encode(Image.fromarray(atlas), codec, quality)
        t_enc = time.perf_counter() - t0
        total = len(blob)
        t0 = time.perf_counter()
        got = crop_tiles(decode(blob), coords, th, tw)
        t_dec = time.perf_counter() - t0
        ssims = [ssim(t, g) for t, g in zip(tiles, got)]
    arr = np.array(ssims)
    return {
        "bytes_total": total,
        "bytes_per_tile": total / len(tiles),
        "ssim_mean": float(arr.mean()),
        "ssim_min": float(arr.min()),
        "ssim_p10": float(np.percentile(arr, 10)),
        "enc_s": round(t_enc, 3),
        "dec_s": round(t_dec, 3),
        "ssims": [round(s, 5) for s in ssims],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--classes", default="emoji,photos")
    ap.add_argument("--counts", default="10,50,200,500")
    ap.add_argument("--codecs", default="png,webp_ll,jxl_ll,jpeg:30,jpeg:50,jpeg:65,jpeg:80,jpeg:90,"
                    "webp:30,webp:50,webp:65,webp:80,webp:90,avif:30,avif:50,avif:65,avif:80,avif:90,"
                    "jxl:30,jxl:50,jxl:65,jxl:80,jxl:90")
    ap.add_argument("--paddings", default="0,8,16")
    args = ap.parse_args()

    outdir = ROOT / "results" / "static" / args.tag
    outdir.mkdir(parents=True, exist_ok=True)
    rows = []
    codecs = [parse_codec(s) for s in args.codecs.split(",")]
    if not HAVE_JXL:
        codecs = [c for c in codecs if not c[0].startswith("jxl")]
        print("WARNING: pillow_jxl missing, skipping JXL")

    for cls in args.classes.split(","):
        max_n = max(int(x) for x in args.counts.split(","))
        all_tiles, _names = load_tiles(cls, max_n)
        for n in (int(x) for x in args.counts.split(",")):
            tiles = all_tiles[:n]
            for codec, q in codecs:
                conds = [("individual", 0)] + [("atlas", p) for p in
                                              (int(x) for x in args.paddings.split(","))]
                for mode, pad in conds:
                    r = run_condition(tiles, codec, q, mode, pad)
                    row = {"class": cls, "n": n, "codec": codec, "quality": q,
                           "mode": mode, "pad": pad, **r}
                    rows.append(row)
                    print(f"{cls} n={n} {codec}:{q} {mode} pad={pad} -> "
                          f"{r['bytes_total']} B, ssim {r['ssim_mean']:.4f}")
                    (outdir / "results.jsonl").open("a").write(json.dumps(row) + "\n")

    with (outdir / "results.json").open("w") as f:
        json.dump(rows, f, indent=1)
    print(f"\nwrote {len(rows)} rows to {outdir}")


if __name__ == "__main__":
    main()
