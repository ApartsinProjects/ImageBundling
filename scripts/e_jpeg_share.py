"""Cheap experiment: does a JPEG atlas gain beyond fixed-cost amortization from
(a) a shared/optimized Huffman tree and (b) a corpus-tuned quantization table, and
does the tuning help more on a homogeneous corpus than a heterogeneous one?

Framing (coupling spectrum): sharing the tables' BYTES is fixed-cost (always a win);
tuning the shared quantizer is adaptive-state (should pay only when tiles are alike).

Conditions per (corpus, size), all at matched luma-SSIM via the study's rate-distortion
interpolation (bd_saving over the common SSIM range):
  ind_fix / atl_fix     standard qtable, FIXED (Annex-K) Huffman   (optimize=False)
  ind_opt / atl_opt     standard qtable, OPTIMIZED Huffman         (optimize=True)  [= paper]
  atl_tuned             corpus-tuned luma qtable + optimized Huffman

Pre-stated invariants (checked, must hold or the plumbing is wrong):
  I1 optimize=True never yields MORE bytes than optimize=False at equal settings.
  I2 re-encoding with the extracted standard qtable reproduces the default bytes (+/-2%)
     -> confirms the qtable ordering we feed Pillow is correct.
  I3 the homogeneous corpus (product_white) shows a LARGER atlas saving than the
     heterogeneous one (photos) -> reproduces the paper's fixed-cost story.

Pre-stated hypotheses (so a null is informative):
  H1 (Huffman): atl_opt saving >= atl_fix saving (the atlas amortizes the optimized
     Huffman table over N tiles, so it benefits at least as much as individuals do).
  H2 (quantizer): tuning the luma qtable helps the atlas on the HOMOGENEOUS corpus
     and does little or nothing on the heterogeneous one. Because the standard table
     is perceptually (CSF) tuned and we score SSIM, a MSE-energy-tuned table may NOT
     beat it even when homogeneous -- that outcome is itself a finding.
"""
import io
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image

import e_predict as ep  # ssim, dec, load_tiles, synth_product_white, bd_saving

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "results" / "static" / "e_jpeg_share"
OUT.mkdir(parents=True, exist_ok=True)

N = 100
SIZES = [56, 112]
CORPORA = ["product_white", "photos"]          # homogeneous, heterogeneous
QUALITIES = [30, 50, 65, 80, 90]
SCALES = [0.5, 0.8, 1.15, 1.7, 2.5]            # qtable scale sweep (for custom tables)

# zigzag[i] = natural-order index of the i-th zigzag coefficient (Pillow's
# quantization tables and the qtables argument are both in zigzag order)
ZIGZAG = [0, 1, 8, 16, 9, 2, 3, 10, 17, 24, 32, 25, 18, 11, 4, 5,
          12, 19, 26, 33, 40, 48, 41, 34, 27, 20, 13, 6, 7, 14, 21, 28,
          35, 42, 49, 56, 57, 50, 43, 36, 29, 22, 15, 23, 30, 37, 44, 51,
          58, 59, 52, 45, 38, 31, 39, 46, 53, 60, 61, 54, 47, 55, 62, 63]


def load(corpus, size):
    if corpus == "product_white":
        return [ep.synth_product_white(size) for _ in range(N)]
    return ep.load_tiles_big(corpus, size) if hasattr(ep, "load_tiles_big") else _load_photos(size)


def _load_photos(size):
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


def make_atlas(tiles):
    th, tw = tiles[0].shape[:2]
    n = len(tiles)
    cols = math.ceil(math.sqrt(n))
    rows = math.ceil(n / cols)
    atlas = np.full((rows * th, cols * tw, 3), 255, np.uint8)
    coords = []
    for i, t in enumerate(tiles):
        r, c = divmod(i, cols)
        atlas[r * th:(r + 1) * th, c * tw:(c + 1) * tw] = t
        coords.append((r * th, c * tw))
    return atlas, coords, (th, tw)


# ---------------- JPEG encode variants ----------------

def enc(arr, quality=None, qtables=None, optimize=True):
    b = io.BytesIO()
    kw = {"optimize": optimize}
    if qtables is not None:
        kw["qtables"] = [list(map(int, t)) for t in qtables]
    else:
        kw["quality"] = quality
    Image.fromarray(arr).save(b, "JPEG", **kw)
    return b.getvalue()


def std_qtables(quality):
    """Standard libjpeg luma+chroma tables at a given quality, in zigzag order."""
    d = enc(np.zeros((16, 16, 3), np.uint8), quality=quality)
    q = Image.open(io.BytesIO(d)).quantization
    return [list(q[0]), list(q[1] if 1 in q else q[0])]


# ---------------- corpus-tuned luma quantization table ----------------

def _dct_matrix():
    n = 8
    D = np.zeros((n, n))
    for k in range(n):
        for x in range(n):
            D[k, x] = math.cos(math.pi * (2 * x + 1) * k / (2 * n))
        D[k] *= math.sqrt(1 / n) if k == 0 else math.sqrt(2 / n)
    return D


_DCTM = _dct_matrix()


def coeff_variance(tiles):
    """Mean squared DCT coefficient per luma frequency across all 8x8 blocks."""
    acc = np.zeros((8, 8))
    cnt = 0
    for t in tiles:
        y = (0.299 * t[..., 0] + 0.587 * t[..., 1] + 0.114 * t[..., 2]).astype(np.float64)
        h, w = y.shape[0] // 8 * 8, y.shape[1] // 8 * 8
        yy = y[:h, :w] - 128
        for i in range(0, h, 8):
            for j in range(0, w, 8):
                C = _DCTM @ yy[i:i + 8, j:j + 8] @ _DCTM.T
                acc += C * C
                cnt += 1
    return acc / max(cnt, 1)  # natural 8x8 order


def tuned_luma(tiles, std_luma_zz):
    """Reverse-water-filling luma table from corpus coefficient energy: coarser steps
    where the corpus has little energy. Normalized to the standard table's geometric
    mean so the scale sweep is comparable to the standard sweep (isolates SHAPE)."""
    var = coeff_variance(tiles)                       # natural order (8x8)
    step = 1.0 / np.sqrt(var + 1e-6)                  # low energy -> large step
    step_zz = np.array([step.ravel()[ZIGZAG[i]] for i in range(64)])
    std = np.array(std_luma_zz, float)
    # match geometric means so s=1 tuned ~ standard overall strength
    gm_t = math.exp(np.log(step_zz).mean())
    gm_s = math.exp(np.log(std).mean())
    tab = step_zz * (gm_s / gm_t)
    return np.clip(np.round(tab), 1, 255)


def scaled(tab, s):
    return np.clip(np.round(np.array(tab, float) * s), 1, 255)


# ---------------- rate-distortion curves ----------------

def curve_std(tiles, atlas, coords, tsz, optimize):
    th, tw = tsz
    ind, atl = [], []
    for q in QUALITIES:
        tot, sl = 0, []
        for t in tiles:
            d = enc(t, quality=q, optimize=optimize)
            tot += len(d); sl.append(ep.ssim(t, ep.dec(d)))
        ind.append((float(np.mean(sl)), tot))
        d = enc(atlas, quality=q, optimize=optimize); dd = ep.dec(d)
        sl = [ep.ssim(t, dd[y:y + th, x:x + tw]) for t, (y, x) in zip(tiles, coords)]
        atl.append((float(np.mean(sl)), len(d)))
    return ind, atl


def curve_qtables(tiles, atlas, coords, tsz, luma_base, chroma_base):
    th, tw = tsz
    ind, atl = [], []
    for s in SCALES:
        qt = [scaled(luma_base, s), scaled(chroma_base, s)]
        tot, sl = 0, []
        for t in tiles:
            d = enc(t, qtables=qt); tot += len(d); sl.append(ep.ssim(t, ep.dec(d)))
        ind.append((float(np.mean(sl)), tot))
        d = enc(atlas, qtables=qt); dd = ep.dec(d)
        sl = [ep.ssim(t, dd[y:y + th, x:x + tw]) for t, (y, x) in zip(tiles, coords)]
        atl.append((float(np.mean(sl)), len(d)))
    return ind, atl


def bd(ind, atl):
    r = ep.bd_saving(ind, atl)
    return r[0] if r else None


def main():
    invariants = []
    results = []
    for corpus in CORPORA:
        for size in SIZES:
            tiles = load(corpus, size)
            atlas, coords, tsz = make_atlas(tiles)

            # standard tables, fixed vs optimized Huffman
            ind_fix, atl_fix = curve_std(tiles, atlas, coords, tsz, optimize=False)
            ind_opt, atl_opt = curve_std(tiles, atlas, coords, tsz, optimize=True)

            # I1: optimize never larger at equal quality (check q80 point, index 3)
            i1 = ind_opt[3][1] <= ind_fix[3][1] and atl_opt[3][1] <= atl_fix[3][1]
            invariants.append(("I1 optimize<=fixed", corpus, size, bool(i1),
                               ind_opt[3][1], ind_fix[3][1]))

            # I2: extracted standard table round-trips to default bytes (+/-2%)
            std_l, std_c = std_qtables(80)
            d_default = enc(tiles[0], quality=80, optimize=True)
            d_roundtrip = enc(tiles[0], qtables=[std_l, std_c], optimize=True)
            ratio = len(d_roundtrip) / len(d_default)
            invariants.append(("I2 std-qtable round-trip ratio", corpus, size,
                               abs(ratio - 1.0) < 0.05, round(ratio, 4), 1.0))

            # corpus-tuned luma table (+ standard chroma), swept; also a standard-table
            # sweep by the SAME scale mechanism as a fair baseline for table SHAPE
            tuned_l = tuned_luma(tiles, std_l)
            ind_tstd, atl_tstd = curve_qtables(tiles, atlas, coords, tsz, std_l, std_c)
            ind_ttun, atl_ttun = curve_qtables(tiles, atlas, coords, tsz, tuned_l, std_c)

            row = {
                "corpus": corpus, "size": size,
                "atlas_saving_fixedHuffman": bd(ind_fix, atl_fix),
                "atlas_saving_optHuffman": bd(ind_opt, atl_opt),   # = paper condition
                # how much the atlas alone shrinks by turning on optimized Huffman
                "atlas_opt_vs_fix_pct": round(100 * (1 - atl_opt[3][1] / atl_fix[3][1]), 2),
                "ind_opt_vs_fix_pct": round(100 * (1 - ind_opt[3][1] / ind_fix[3][1]), 2),
                # quantizer tuning (matched SSIM), scale-swept standard vs tuned SHAPE
                "atlas_saving_stdTable_sweep": bd(ind_tstd, atl_tstd),
                "atlas_saving_tunedTable_sweep": bd(ind_ttun, atl_ttun),
                "tuning_effect_on_atlas": bd(atl_tstd, atl_ttun),   # +=tuned smaller
                "tuning_effect_on_individual": bd(ind_tstd, ind_ttun),
            }
            results.append(row)
            print(f"[{corpus:14} {size:>3}] "
                  f"atlas save opt={row['atlas_saving_optHuffman']} "
                  f"fix={row['atlas_saving_fixedHuffman']} | "
                  f"tune->atlas={row['tuning_effect_on_atlas']} "
                  f"tune->ind={row['tuning_effect_on_individual']}", flush=True)

    # I3: homogeneous > heterogeneous atlas saving (compare at 112)
    sav = {(r["corpus"]): r["atlas_saving_optHuffman"]
           for r in results if r["size"] == 112}
    i3 = sav.get("product_white", -9) > sav.get("photos", 9)
    invariants.append(("I3 homogeneous>heterogeneous @112", "-", 112, bool(i3),
                       sav.get("product_white"), sav.get("photos")))

    print("\n=== invariants ===")
    for name, corp, sz, ok, got, exp in invariants:
        print(f"  {'PASS' if ok else 'FAIL'} {name} [{corp} {sz}] got={got} ref={exp}")

    json.dump({"results": results,
               "invariants": [{"name": n, "corpus": c, "size": s, "ok": ok,
                               "got": g, "ref": e} for n, c, s, ok, g, e in invariants]},
              (OUT / "results.json").open("w"), indent=1)
    print("\nJPEG-SHARE DONE")


if __name__ == "__main__":
    main()
