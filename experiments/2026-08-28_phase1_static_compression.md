# Phase 1: static compression study (atlas vs individual, no network)

Status: in_progress

## Hypothesis
H1: total bytes(atlas) < sum bytes(individual) at matched per-tile SSIM, with the gap
growing as tile size shrinks and N grows, largest for homogeneous flat art (emoji),
and codec-dependent (largest for AVIF given its ~303 B container floor, smallest for JXL
at 24 B). Falsified if savings are ~0 or negative across the board at matched quality.

## Setup
- Assets: 520 Twemoji 72x72 PNGs (flat art, alpha composited over white), 520 Lorem
  Picsum 224x224 JPEG thumbnails (photos), deterministic lists (sorted filenames).
- Codecs (Pillow 12.2, Python 3.14 + pillow-jxl-plugin): png, webp_ll, jxl_ll (lossless);
  jpeg/webp/avif/jxl at quality {30,50,65,80,90}.
- Conditions: individual files vs grid atlas with edge-replicated padding {0,8,16} px.
- Metric: per-tile luma SSIM (8x8 box window) computed after cropping tiles back out of
  the decoded artifact (captures atlas border bleed). Bytes = encoded size.
- Matched-quality comparison: log-linear interpolation of bytes at SSIM targets
  {0.95, 0.97, 0.99} along each condition's quality ladder (aggregate_static.py).
- Hardware: local CPU (Windows). Code: scripts/static_study.py at the committed revision.

## Invariants stated in advance
1. Lossless codecs: SSIM exactly 1.0 in every condition. (smoke1: PASS)
2. Atlas of N=1, pad=0 is byte-identical (grid degenerates to the image itself) to the
   individual file. (smoke_inv1: PASS, jpeg and avif byte-identical)
3. More padding never decreases atlas bytes at fixed quality.
4. Savings for 72px tiles >= savings for 224px tiles at the same codec and N.

## Procedure
1. `bash scripts/fetch_assets.sh` (deterministic asset lists).
2. `python scripts/static_study.py --tag phase1_<class>` full sweep per class.
3. `python scripts/aggregate_static.py --tag phase1_<class>`.

## Headline numbers
Atlas saving vs individual files at matched per-tile SSIM 0.97 (pad 0):

| class | n | AVIF | JPEG | JXL | WebP | PNG (ll) | WebP ll | JXL ll |
|---|---|---|---|---|---|---|---|---|
| emoji 72px | 10 | 48.0% | 19.4% | 8.5% | ~15%* | 4.3% | -0.2% | -9.9% |
| emoji 72px | 50 | 54.9% | 26.3% | 23.3% | 8.3% | 5.4% | 5.4% | -5.3% |
| emoji 72px | 200 | 55.9% | 25.1% | 24.2% | 15.2% | -3.1% | -4.7% | -43.9% |
| emoji 72px | 500 | >=60.0% | 26.3% | 25.8% | 8.2% | -5.7% | -3.6% | -35.4% |
| photos 224px | 500 | 5.8% | 3.0% | 7.1% | -8.5% | -3.6% | -4.9% | -1.7% |

(*n=10 webp interpolation range limited; raw-ladder comparison shown.)
Padding tax (AVIF, emoji, n=200): pad 0 -> 55.9%, pad 8 -> 49.7%, pad 16 -> 44.6%.
Audit: 368 rows per class, metrics in range, lossless SSIM exactly 1.0, no contamination
paths (single deterministic asset list), invariants 1-2 pass (smoke1, smoke_inv1).

## Artifacts
- results/static/smoke1/, results/static/smoke_inv1/ (pipeline validation)
- results/static/phase1_*/results.jsonl (full per-condition rows incl. per-tile SSIMs)

## Conclusion
H1 supported with a sharp scope: at matched quality, atlasing pays on SMALL LOSSY tiles,
scaling with the container-overhead-to-content ratio. AVIF gains most (its ~303 B/file
container floor dominates 1-3 KB tiles): >=60% at n=500 emoji. JPEG and lossy JXL gain
~25%; WebP least among lossy. For 224px photo tiles the gain shrinks to 3-7% (AVIF/JXL)
and WebP atlasing is NET NEGATIVE (-8.5%), as is all lossless atlasing at n>=200 (JXL
lossless down to -44%: per-image modular-mode adaptation beats one global model; confirmed
at max effort, not an encoder-effort artifact). Practical rule from Phase 1: bundle small
flat lossy assets (icons/emoji), served as AVIF; do not bundle lossless assets or
200px+ photos for byte reasons (network effects are Phase 2's question). Padding costs
~6pp per 8px step (AVIF), so block alignment must earn its keep in Phase 3's bleed study.
