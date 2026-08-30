"""Cross-corpus, cross-codec matched-quality crossover (review items W7 + W8).

W7: show the photo atlas-vs-individual crossover is a general regime, not a property of one
image population, by repeating it on several independent natural-photo corpora.
W8: add AVIF to the core crossover alongside JPEG and WebP.

For each (corpus, tile size, codec) we sweep a quality ladder, measure individual-file
bytes vs grid-atlas bytes and mean per-tile luma SSIM, then interpolate bytes at matched
SSIM 0.97 (the main study's protocol) and report the atlas saving. We then aggregate
across corpora (median and range) so a corpus-level effect, not a single dataset, carries
the claim.

Photo corpora (independent natural populations):
  picsum        - Lorem Picsum (the study's primary photo source)
  flickr        - loremflickr generic real Flickr photos
  flickr_nature - loremflickr nature category (distinct visual statistics)
  flickr_food   - loremflickr food category (close-up, saturated; distinct statistics)
"""
import argparse
import gc
import json
from pathlib import Path

import numpy as np
from PIL import Image

import static_study as ss

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "results" / "static" / "e_crosscorpus"
OUT.mkdir(parents=True, exist_ok=True)

CORPORA = [
    ("picsum", ROOT / "assets" / "photos"),
    ("flickr", ROOT / "assets_oos" / "flickr"),
    ("flickr_nature", ROOT / "assets_oos" / "flickr_nature"),
    ("flickr_food", ROOT / "assets_oos" / "flickr_food"),
]
SIZES = [56, 112, 224]
CODECS = ["jpeg", "webp", "avif"]
QUALITIES = [30, 50, 65, 80, 90]
N = 60
TARGET = 0.97
AVIF_SPEED = 8   # faster AVIF encode; matched-quality comparison is speed-insensitive


def load_corpus(d, n, size):
    files = sorted(p for p in Path(d).iterdir()
                   if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"))[:n]
    tiles = []
    for f in files:
        im = Image.open(f).convert("RGB").resize((size, size), Image.LANCZOS)
        tiles.append(np.asarray(im))
    return tiles


def encode(img, codec, q):
    """Encode; return bytes, or None if the codec runs out of memory (low-RAM host)."""
    import io
    buf = io.BytesIO()
    try:
        if codec == "jpeg":
            img.save(buf, "JPEG", quality=q, optimize=True)
        elif codec == "webp":
            img.save(buf, "WEBP", quality=q, method=6)
        elif codec == "avif":
            img.save(buf, "AVIF", quality=q, speed=AVIF_SPEED)
    except (RuntimeError, MemoryError):
        return None
    return buf.getvalue()


def curve(tiles, codec):
    """Return {'individual':[(ssim,bytes)...], 'atlas':[...]} over the quality ladder,
    or None if any encode ran out of memory."""
    th, tw, _ = tiles[0].shape
    atlas_arr, coords = ss.build_atlas(tiles, 0)
    out = {"individual": [], "atlas": []}
    for q in QUALITIES:
        tot, ss_list = 0, []
        for t in tiles:
            b = encode(Image.fromarray(t), codec, q)
            if b is None:
                return None
            tot += len(b)
            ss_list.append(ss.ssim(t, ss.decode(b)))
        out["individual"].append((float(np.mean(ss_list)), tot))
        b = encode(Image.fromarray(atlas_arr), codec, q)
        if b is None:
            return None
        got = ss.crop_tiles(ss.decode(b), coords, th, tw)
        ss_list = [ss.ssim(t, g) for t, g in zip(tiles, got)]
        out["atlas"].append((float(np.mean(ss_list)), len(b)))
        gc.collect()
    return out


def bytes_at(points, target):
    pts = sorted(points)
    xs = np.array([p[0] for p in pts])
    bb = np.log(np.array([float(p[1]) for p in pts]))
    if target < xs[0] or target > xs[-1]:
        return None
    return float(np.exp(np.interp(target, xs, bb)))


def run_unit(cname, cdir, size):
    """Process one (corpus, size) unit across all codecs; append rows to results.jsonl.
    Run per-unit in a fresh process so AVIF memory is released between units."""
    tiles = load_corpus(cdir, N, size)
    with (OUT / "results.jsonl").open("a") as fh:
        for codec in CODECS:
            c = curve(tiles, codec)
            if c is None:
                row = {"corpus": cname, "size": size, "codec": codec, "n": len(tiles),
                       "saving_pct": None, "bytes_individual": None, "bytes_atlas": None,
                       "curve": None, "note": "encode OOM, skipped"}
            else:
                bi = bytes_at(c["individual"], TARGET)
                ba = bytes_at(c["atlas"], TARGET)
                saving = round(100 * (1 - ba / bi), 2) if (bi and ba) else None
                row = {"corpus": cname, "size": size, "codec": codec, "n": len(tiles),
                       "saving_pct": saving, "bytes_individual": round(bi) if bi else None,
                       "bytes_atlas": round(ba) if ba else None, "curve": c}
            fh.write(json.dumps(row) + "\n")
            print(f"{cname:14} {size:>3}px {codec:5} saving="
                  f"{row['saving_pct'] if row['saving_pct'] is not None else 'n/a'}", flush=True)
            gc.collect()


def aggregate():
    rows = [json.loads(l) for l in (OUT / "results.jsonl").open()]
    json.dump(rows, (OUT / "results.json").open("w"), indent=1)
    print("\n=== cross-corpus matched-SSIM-0.97 atlas saving (%) ===")
    print(f"{'size':>4} {'codec':5} {'median':>7} {'min':>7} {'max':>7}  per-corpus")
    agg = []
    for size in SIZES:
        for codec in CODECS:
            vals = [(r["corpus"], r["saving_pct"]) for r in rows
                    if r["size"] == size and r["codec"] == codec and r["saving_pct"] is not None]
            if not vals:
                continue
            svals = [v for _, v in vals]
            med, lo, hi = np.median(svals), min(svals), max(svals)
            agg.append({"size": size, "codec": codec, "median": round(float(med), 2),
                        "min": lo, "max": hi, "n_corpora": len(vals),
                        "per_corpus": dict(vals)})
            pc = " ".join(f"{c}={v:+.0f}" for c, v in vals)
            print(f"{size:>4} {codec:5} {med:>7.1f} {lo:>7.1f} {hi:>7.1f}  {pc}")
    json.dump({"rows": rows, "aggregate": agg}, (OUT / "summary.json").open("w"), indent=1)
    print("CROSSCORPUS DONE")


if __name__ == "__main__":
    main()
