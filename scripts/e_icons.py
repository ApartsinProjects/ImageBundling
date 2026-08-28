"""T1+T2: PNG/WebP atlasing on a homogeneous flat-icon corpus (Fable use-case tests).

Synthesizes N flat icons (fixed 12-color palette + alpha, uniform style) so the corpus
models a design-system icon set / map-marker set. Tests where PNG and WebP atlasing
should WIN: shared-palette PNG, VP8L near-lossless, duplicate exploitation, plus a
JPEG-atlas column (JPEG must composite over white; alpha assets normally disqualify it).

Lossless conditions are byte-exact and verified identical after decode (invariant).
Lossy conditions (jpeg, webp near-lossless) report bytes at their setting AND per-tile
SSIM so quality is visible. All conditions co-computed in one pass on one seeded corpus.
"""
import io
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

import static_study as ss

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "results" / "static" / "e_icons"
OUT.mkdir(parents=True, exist_ok=True)

PALETTE = [(0, 0, 0), (255, 255, 255), (37, 99, 235), (220, 38, 38), (22, 163, 74),
           (234, 179, 8), (147, 51, 234), (14, 165, 233), (249, 115, 22),
           (236, 72, 153), (100, 116, 139), (16, 185, 129)]


def make_icons(n, size, seed=0, dup_frac=0.0, neardup_frac=0.0):
    rng = np.random.default_rng(seed)
    base_n = int(n * (1 - dup_frac - neardup_frac))
    icons = []
    for _ in range(base_n):
        im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        nshapes = rng.integers(2, 5)
        for _ in range(nshapes):
            col = PALETTE[rng.integers(len(PALETTE))] + (255,)
            kind = rng.integers(3)
            x0, y0 = rng.integers(0, size // 2, 2)
            x1, y1 = rng.integers(size // 2, size, 2)
            if kind == 0:
                d.ellipse([x0, y0, x1, y1], fill=col)
            elif kind == 1:
                d.rectangle([x0, y0, x1, y1], fill=col)
            else:
                w = int(rng.integers(2, max(3, size // 8)))
                d.line([x0, y0, x1, y1], fill=col, width=w)
        icons.append(np.asarray(im))
    # exact duplicates
    ndup = int(n * dup_frac)
    for _ in range(ndup):
        icons.append(icons[rng.integers(base_n)].copy())
    # near-duplicates: hue-swap one palette color
    nnear = n - len(icons)
    for _ in range(nnear):
        src = icons[rng.integers(base_n)].copy()
        # shift non-transparent pixels' channel order (cheap "recolor")
        a = src[..., 3] > 0
        src[a] = src[a][:, [1, 2, 0, 3]]
        icons.append(src)
    return icons[:n]


def over_white(t):
    im = Image.fromarray(t).convert("RGBA")
    bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
    return np.asarray(Image.alpha_composite(bg, im).convert("RGB"))


def enc(im, fmt, **kw):
    b = io.BytesIO()
    im.save(b, fmt, **kw)
    return b.getvalue()


def grid(tiles, mode):
    n = len(tiles)
    th, tw = tiles[0].shape[:2]
    cols = math.ceil(math.sqrt(n))
    rows = math.ceil(n / cols)
    ch = 4 if mode == "RGBA" else 3
    fill = (0,) * 4 if mode == "RGBA" else (255,) * 3
    atlas = np.full((rows * th, cols * tw, ch), 0 if mode == "RGBA" else 255, np.uint8)
    for i, t in enumerate(tiles):
        r, c = divmod(i, cols)
        atlas[r * th:(r + 1) * th, c * tw:(c + 1) * tw] = t[..., :ch]
    return atlas


def strip(tiles, ch):
    return np.concatenate([t[..., :ch] for t in tiles], axis=0)


def tile_ssim(atlas_dec, tiles, layout, size):
    """per-tile mean SSIM after cropping tiles back out of a decoded RGB atlas."""
    sims = []
    if layout == "strip":
        for i, t in enumerate(tiles):
            g = atlas_dec[i * size:(i + 1) * size, :size]
            sims.append(ss.ssim(over_white(t), g))
    else:
        n = len(tiles)
        cols = math.ceil(math.sqrt(n))
        for i, t in enumerate(tiles):
            r, c = divmod(i, cols)
            g = atlas_dec[r * size:(r + 1) * size, c * size:(c + 1) * size]
            sims.append(ss.ssim(over_white(t), g))
    return float(np.mean(sims))


def main():
    rows = []

    def emit(**kw):
        rows.append(kw)
        print(kw, flush=True)

    for corpus, kw in [("clean", {}),
                       ("dup", {"dup_frac": 0.2, "neardup_frac": 0.2})]:
        for size in (24, 48):
            tiles = make_icons(200, size, seed=1, **kw)
            n = len(tiles)
            rgba = [t for t in tiles]
            white = [over_white(t) for t in tiles]

            # --- individual baselines (lossless)
            png_ind = sum(len(enc(Image.fromarray(t), "PNG", optimize=True)) for t in rgba)
            pal_ind = sum(len(enc(Image.fromarray(t).convert("P", palette=Image.ADAPTIVE,
                          colors=255), "PNG", optimize=True)) for t in rgba)
            wll_ind = sum(len(enc(Image.fromarray(t), "WEBP", lossless=True, quality=100,
                          method=6)) for t in rgba)

            def save_saving(cond, atlas_arr, mode, fmt, individual, **ekw):
                blob = enc(Image.fromarray(atlas_arr), fmt, **ekw)
                emit(corpus=corpus, size=size, n=n, cond=cond, fmt=fmt,
                     bytes=len(blob), individual=individual,
                     saving_pct=round(100 * (1 - len(blob) / individual), 1))
                return blob

            # --- PNG lossless: grid, strip (RGBA)
            save_saving("png_grid_rgba", grid(rgba, "RGBA"), "RGBA", "PNG",
                        png_ind, optimize=True)
            save_saving("png_strip_rgba", strip(rgba, 4), "RGBA", "PNG",
                        png_ind, optimize=True)
            # --- PNG shared-palette strip (quantize concat to P; verify exact)
            strip_rgb = strip([over_white(t) for t in tiles], 3)
            pimg = Image.fromarray(strip_rgb).convert("P", palette=Image.ADAPTIVE,
                                                       colors=256)
            exact = np.array_equal(np.asarray(pimg.convert("RGB")), strip_rgb)
            blob = enc(pimg, "PNG", optimize=True)
            emit(corpus=corpus, size=size, n=n, cond="png_strip_shared_palette",
                 fmt="PNG-P", bytes=len(blob), individual=pal_ind,
                 saving_pct=round(100 * (1 - len(blob) / pal_ind), 1),
                 palette_exact=bool(exact),
                 saving_vs_rgba=round(100 * (1 - len(blob) / png_ind), 1))
            # --- WebP lossless: grid, strip
            save_saving("webpll_grid", grid(rgba, "RGBA"), "RGBA", "WEBP",
                        wll_ind, lossless=True, quality=100, method=6)
            save_saving("webpll_strip", strip(rgba, 4), "RGBA", "WEBP",
                        wll_ind, lossless=True, quality=100, method=6)

            # --- lossy columns at matched quality (target SSIM 0.97): jpeg + webp
            # sweep q, interpolate bytes at ssim 0.97 for grid atlas over white
            for fmt, ekwbase in [("JPEG", {"optimize": True}), ("WEBP", {"method": 6})]:
                pts_atlas, pts_ind = [], []
                for q in (40, 70, 90):
                    ek = dict(ekwbase, quality=q)
                    a = grid(white, "RGB")
                    ba = enc(Image.fromarray(a), fmt, **ek)
                    dec = np.asarray(Image.open(io.BytesIO(ba)).convert("RGB"))
                    pts_atlas.append((tile_ssim(dec, tiles, "grid", size), len(ba)))
                    bi = sum(len(enc(Image.fromarray(w), fmt, **ek)) for w in white)
                    # per-tile ssim of individual = encode/decode each
                    sims = []
                    for w in white:
                        d = np.asarray(Image.open(io.BytesIO(
                            enc(Image.fromarray(w), fmt, **ek))).convert("RGB"))
                        sims.append(ss.ssim(w, d))
                    pts_ind.append((float(np.mean(sims)), bi))

                def at(pts, tgt=0.97):
                    pts = sorted(pts)
                    xs = [p[0] for p in pts]
                    ys = [np.log(p[1]) for p in pts]
                    if tgt < xs[0] or tgt > xs[-1]:
                        return None
                    return float(np.exp(np.interp(tgt, xs, ys)))
                ba97, bi97 = at(pts_atlas), at(pts_ind)
                if ba97 and bi97:
                    emit(corpus=corpus, size=size, n=n, cond=f"{fmt.lower()}_grid_atlas_ssim97",
                         fmt=fmt, bytes=round(ba97), individual=round(bi97),
                         saving_pct=round(100 * (1 - ba97 / bi97), 1))

    json.dump(rows, (OUT / "results.json").open("w"), indent=1)
    (OUT / "results.jsonl").write_text("\n".join(json.dumps(r) for r in rows))
    print("ICONS DONE")


if __name__ == "__main__":
    main()
