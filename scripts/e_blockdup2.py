"""Codec-domain block dedup: encode each 8x8 luma block the way JPEG does (DCT -> quantize
by the standard table at quality Q -> round), then hash the quantized coefficients and count
COLLISIONS (blocks that quantize to the same code = the codec stores them identically).

Two hashes:
  full  quantized DC+AC  -> exact codec-domain duplicate
  AC    quantized AC only (DC zeroed) -> same TEXTURE at any brightness (brightness is the
        DC term, coded separately/cheaply), so this is the brightness-invariant texture-dup

Lower Q = coarser quantization = more collisions (smaller catalogue) but more distortion.
The question: at a quality that still looks fine (Q~75-90), do TEXTURED blocks collide enough
for a block catalogue to pay, or are they still ~unique?

Sets: ImageNet-diverse and product-on-white (control).
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import e_predict as ep
import e_jpeg_share as es
import e_pivot_validate as pv

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "results" / "static" / "e_blockdup2"
OUT.mkdir(parents=True, exist_ok=True)

SIZE = 128
NIMG = 400
QUALITIES = [90, 75, 50]
FLAT_VAR = 25.0

# 8x8 DCT-II matrix
_n = 8
_D = np.zeros((_n, _n))
for _k in range(_n):
    for _x in range(_n):
        _D[_k, _x] = np.cos(np.pi * (2 * _x + 1) * _k / (2 * _n))
    _D[_k] *= np.sqrt(1 / _n) if _k == 0 else np.sqrt(2 / _n)


def std_nat(q):
    zz = es.std_qtables(q)[0]
    nat = np.zeros(64)
    for i, z in enumerate(zz):
        nat[es.ZIGZAG[i]] = z
    return nat.reshape(8, 8)


def image_blocks(img):
    y = (0.299 * img[..., 0] + 0.587 * img[..., 1] + 0.114 * img[..., 2]).astype(np.float64)
    h, w = y.shape[0] // 8 * 8, y.shape[1] // 8 * 8
    y = y[:h, :w] - 128
    nb_r, nb_c = h // 8, w // 8
    blocks = y.reshape(nb_r, 8, nb_c, 8).transpose(0, 2, 1, 3).reshape(-1, 8, 8)
    return blocks  # (nblocks, 8, 8)


def analyze(images, label):
    var_all = []
    blk_all = []
    for img in images:
        b = image_blocks(img)
        blk_all.append(b)
        var_all.append(b.var(axis=(1, 2)))
    B = np.concatenate(blk_all)              # (N,8,8)
    V = np.concatenate(var_all)              # (N,)
    total = len(B)
    tex = V >= FLAT_VAR
    out = {"set": label, "images": len(images), "blocks": int(total),
           "flat_fraction": round(float((~tex).mean()), 3), "by_quality": {}}
    # batch DCT for all blocks
    C = np.einsum('ij,njk,lk->nil', _D, B, _D)   # (N,8,8) DCT coeffs
    for q in QUALITIES:
        Q = std_nat(q)
        qc = np.round(C / Q).astype(np.int16)     # quantized coefficients
        full = qc.reshape(total, 64)
        ac = full.copy(); ac[:, 0] = 0            # zero DC (natural-order index 0 is DC)
        def dedup(rows, mask=None):
            r = rows if mask is None else rows[mask]
            if len(r) == 0:
                return 0.0
            u = len({row.tobytes() for row in r})
            return round(1 - u / len(r), 4), len(r), u
        f_all = dedup(full); a_all = dedup(ac)
        f_tex = dedup(full, tex); a_tex = dedup(ac, tex)
        a_flat = dedup(ac, ~tex)
        out["by_quality"][q] = {
            "full_dup_rate": f_all[0], "AC_dup_rate": a_all[0],
            "full_dup_rate_textured": f_tex[0], "AC_dup_rate_textured": a_tex[0],
            "AC_dup_rate_flat": a_flat[0],
            "unique_full": f_all[2], "unique_AC": a_all[2],
        }
    return out


def main():
    pool = pv.build_pool(SIZE)[:NIMG]
    prod = [ep.synth_product_white(SIZE) for _ in range(NIMG)]
    results = [analyze(pool, "imagenet_diverse"), analyze(prod, "product_on_white")]
    json.dump(results, (OUT / "results.json").open("w"), indent=1)
    for r in results:
        print(f"\n=== {r['set']}  ({r['blocks']:,} blocks, flat {r['flat_fraction']*100:.0f}%) ===")
        print(f"  {'Q':>4} | {'full-dup':>9} {'AC-dup':>7} | {'full-dup(tex)':>13} "
              f"{'AC-dup(tex)':>11} | {'AC-dup(flat)':>12} | uniqAC")
        for q in QUALITIES:
            b = r["by_quality"][q]
            print(f"  {q:>4} | {b['full_dup_rate']*100:8.2f}% {b['AC_dup_rate']*100:6.2f}% | "
                  f"{b['full_dup_rate_textured']*100:12.2f}% {b['AC_dup_rate_textured']*100:10.2f}% | "
                  f"{b['AC_dup_rate_flat']*100:11.2f}% | {b['unique_AC']:,}")
    print("\nBLOCKDUP2 DONE")


if __name__ == "__main__":
    main()
