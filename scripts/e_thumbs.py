"""T3 + T4: e-commerce thumbnail walls and avatar walls (Fable use-case tests).

T3 product thumbnails: photos center-cropped onto a white background (models the
flat-background property of real catalog shots), swept over 48/64/80/96/112 px, WebP
lossy atlas vs individual at matched per-tile SSIM 0.97, with a JPEG-atlas column.
Prediction: double-digit win at 48-64px, break-even nearer 110-120px on white bg.

T4 avatar wall: 60 unique face-ish crops rendered into a 200-slot comment thread with
a Zipf popularity distribution (top avatar repeats ~25x) plus 10% flat placeholder.
Compares (a) individual per UNIQUE, (b) atlas of uniques + coord map (explicit dedup),
(c) atlas of all 200 slots (no explicit dedup) to show lossy VP8 recovers ~none of the
duplicate redundancy. Matched SSIM 0.97, 32/48px.
"""
import io
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

import static_study as ss

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "results" / "static" / "e_thumbs"
OUT.mkdir(parents=True, exist_ok=True)


def product_on_white(arr, size, margin=0.12):
    """Center the (downscaled) photo on a white square with margin -> catalog look."""
    inner = int(size * (1 - 2 * margin))
    im = Image.fromarray(arr).resize((inner, inner), Image.LANCZOS)
    canvas = Image.new("RGB", (size, size), (255, 255, 255))
    off = (size - inner) // 2
    canvas.paste(im, (off, off))
    return np.asarray(canvas)


def face_crop(arr, size):
    """Center square crop then resize -> avatar-like."""
    h, w, _ = arr.shape
    s = min(h, w)
    y0, x0 = (h - s) // 2, (w - s) // 2
    im = Image.fromarray(arr[y0:y0 + s, x0:x0 + s]).resize((size, size), Image.LANCZOS)
    return np.asarray(im)


def placeholder(size):
    im = Image.new("RGB", (size, size), (226, 232, 240))
    d = ImageDraw.Draw(im)
    d.ellipse([size * .3, size * .18, size * .7, size * .55], fill=(148, 163, 184))
    d.ellipse([size * .18, size * .6, size * .82, size * 1.1], fill=(148, 163, 184))
    return np.asarray(im)


def enc(arr, fmt, **kw):
    b = io.BytesIO()
    Image.fromarray(arr).save(b, fmt, **kw)
    return b.getvalue()


def grid(tiles):
    n = len(tiles)
    th, tw = tiles[0].shape[:2]
    cols = math.ceil(math.sqrt(n))
    rows = math.ceil(n / cols)
    atlas = np.full((rows * th, cols * tw, 3), 255, np.uint8)
    coords = []
    for i, t in enumerate(tiles):
        r, c = divmod(i, cols)
        atlas[r * th:(r + 1) * th, c * tw:(c + 1) * tw] = t
        coords.append((c * tw, r * th))
    return atlas, coords


def crop_back(dec, coords, size):
    return [dec[y:y + size, x:x + size] for (x, y) in coords]


def matched_saving(tiles, fmt, target=0.97):
    """Interpolated atlas-vs-individual saving at SSIM target for a lossy fmt.
    Dense ladder + bracket check: returns saving only if BOTH curves span the target."""
    size = tiles[0].shape[0]
    pa, pi = [], []
    for q in (20, 35, 50, 60, 70, 80, 90, 95):
        ek = {"quality": q} if fmt == "WEBP" else {"quality": q, "optimize": True}
        if fmt == "WEBP":
            ek["method"] = 6
        atlas, coords = grid(tiles)
        ba = enc(atlas, fmt, **ek)
        dec = np.asarray(Image.open(io.BytesIO(ba)).convert("RGB"))
        sa = np.mean([ss.ssim(t, g) for t, g in zip(tiles, crop_back(dec, coords, size))])
        pa.append((float(sa), len(ba)))
        bi, si = 0, []
        for t in tiles:
            bt = enc(t, fmt, **ek)
            bi += len(bt)
            si.append(ss.ssim(t, np.asarray(Image.open(io.BytesIO(bt)).convert("RGB"))))
        pi.append((float(np.mean(si)), bi))

    def at(pts):
        pts = sorted(pts)
        xs = [p[0] for p in pts]
        ys = [np.log(p[1]) for p in pts]
        if target < xs[0] or target > xs[-1]:
            return None
        return float(np.exp(np.interp(target, xs, ys)))
    a, i = at(pa), at(pi)
    return (round(a), round(i), round(100 * (1 - a / i), 1)) if a and i else (None, None, None)


def main():
    rows = []

    def emit(**kw):
        rows.append(kw)
        print(kw, flush=True)

    photos, _ = ss.load_tiles("photos", 300)
    # dedup source pool so T3 isn't duplicate-driven
    import hashlib
    seen, pool = set(), []
    for t in photos:
        k = hashlib.md5(t.tobytes()).hexdigest()
        if k not in seen:
            seen.add(k)
            pool.append(t)

    # --- T3 product thumbnails on white
    for size in (48, 64, 80, 96, 112):
        tiles = [product_on_white(pool[i], size) for i in range(100)]
        for fmt in ("WEBP", "JPEG"):
            a, i, s = matched_saving(tiles, fmt)
            if s is not None:
                emit(test="T3", size=size, n=100, fmt=fmt, atlas=a, individual=i,
                     saving_pct=s)

    # --- T4 avatar wall
    rng = np.random.default_rng(3)
    for size in (32, 48):
        uniq = [face_crop(pool[i], size) for i in range(54)]
        uniq += [placeholder(size) for _ in range(6)]  # 60 unique incl placeholders
        # Zipf slot assignment over 200 slots
        ranks = np.arange(1, 61)
        p = (1 / ranks) / np.sum(1 / ranks)
        slots = rng.choice(60, size=200, p=p)
        slot_tiles = [uniq[j] for j in slots]
        n_unique_used = len(set(slots.tolist()))
        for fmt in ("WEBP", "JPEG"):
            # (a) individual per UNIQUE tile actually used
            used = sorted(set(slots.tolist()))
            au, iu, su = matched_saving([uniq[j] for j in used], fmt)  # atlas-of-uniques vs indiv-uniques
            # (c) atlas of all 200 slots
            ac, ic, sc = matched_saving(slot_tiles, fmt)
            emit(test="T4", size=size, fmt=fmt, slots=200, unique_used=n_unique_used,
                 atlas_uniques=au, individual_uniques=iu, saving_dedup_pct=su,
                 atlas_all200=ac, individual_all200=ic, saving_nodedup_pct=sc,
                 # does the codec dedup on its own? all-200 atlas / uniques atlas.
                 # ~1.0 = codec dedups; ~200/uniques = it does not.
                 all200_over_uniques=round(ac / au, 2) if au and ac else None)

    json.dump(rows, (OUT / "results.json").open("w"), indent=1)
    (OUT / "results.jsonl").write_text("\n".join(json.dumps(r) for r in rows))
    print("THUMBS DONE")


if __name__ == "__main__":
    main()
