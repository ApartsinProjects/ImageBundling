"""Measure duplicate-block rates across images (the block-catalogue / VQ premise): what
fraction of 8x8 blocks are EXACT or NEAR duplicates across a collection, split by whether
the block is flat (cheap in JPEG anyway) or textured (where the bytes live)?

If most duplicates are flat blocks, a block catalogue saves little (JPEG already codes flat
blocks in ~1-2 bytes), and textured blocks -- the bulk of the bytes -- are ~unique.

Sets: ImageNet-diverse (the real question) and product-on-white (a control that SHOULD
dedup well, to show the contrast).
"""
import io
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import e_predict as ep
import e_pivot_validate as pv

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "results" / "static" / "e_blockdup"
OUT.mkdir(parents=True, exist_ok=True)

SIZE = 128
NIMG = 400
FLAT_VAR = 25.0          # luma variance below this = "flat" block
QN = 16                  # near-duplicate: quantize luma to steps of QN


def blocks_luma(img):
    y = (0.299 * img[..., 0] + 0.587 * img[..., 1] + 0.114 * img[..., 2]).astype(np.uint8)
    h, w = y.shape[0] // 8 * 8, y.shape[1] // 8 * 8
    for i in range(0, h, 8):
        for j in range(0, w, 8):
            yield y[i:i + 8, j:j + 8]


def analyze(images, label):
    total = 0
    exact = Counter(); near = Counter()
    flat_total = flat_exact_dupe = 0
    tex_total = tex_exact_dupe = 0
    exact_seen = set(); near_seen = set()
    flat_seen = set(); tex_seen = set()
    for img in images:
        for b in blocks_luma(img):
            total += 1
            var = float(b.var())
            eh = b.tobytes()
            nh = (b // QN).tobytes()
            exact[eh] += 1; near[nh] += 1
            if var < FLAT_VAR:
                flat_total += 1
                if eh in flat_seen:
                    flat_exact_dupe += 1
                else:
                    flat_seen.add(eh)
            else:
                tex_total += 1
                if eh in tex_seen:
                    tex_exact_dupe += 1
                else:
                    tex_seen.add(eh)
    uniq_exact = len(exact); uniq_near = len(near)
    res = {
        "set": label, "images": len(images), "blocks": total,
        "flat_fraction": round(flat_total / total, 3),
        "exact_dup_rate": round(1 - uniq_exact / total, 4),
        "near_dup_rate": round(1 - uniq_near / total, 4),
        "exact_dup_rate_flat_blocks": round(flat_exact_dupe / max(flat_total, 1), 4),
        "exact_dup_rate_textured_blocks": round(tex_exact_dupe / max(tex_total, 1), 4),
        "index_bits_per_block_exact": round(float(np.log2(uniq_exact)), 1),
        "index_bits_per_block_near": round(float(np.log2(uniq_near)), 1),
    }
    return res


def main():
    pool = pv.build_pool(SIZE)[:NIMG]
    prod = [ep.synth_product_white(SIZE) for _ in range(NIMG)]
    results = [analyze(pool, "imagenet_diverse"), analyze(prod, "product_on_white")]
    json.dump(results, (OUT / "results.json").open("w"), indent=1)

    for r in results:
        print(f"\n=== {r['set']}  ({r['images']} imgs, {r['blocks']:,} 8x8 luma blocks) ===")
        print(f"  flat-block fraction (var<{FLAT_VAR:g}):  {r['flat_fraction']*100:.1f}%")
        print(f"  EXACT duplicate-block rate:      {r['exact_dup_rate']*100:.2f}%")
        print(f"    among FLAT blocks:             {r['exact_dup_rate_flat_blocks']*100:.2f}%")
        print(f"    among TEXTURED blocks:         {r['exact_dup_rate_textured_blocks']*100:.2f}%")
        print(f"  NEAR duplicate-block rate (q{QN}):  {r['near_dup_rate']*100:.2f}%")
        print(f"  catalogue index cost: {r['index_bits_per_block_exact']} bits/block exact,"
              f" {r['index_bits_per_block_near']} bits/block near")
    print("\nBLOCKDUP DONE")


if __name__ == "__main__":
    main()
