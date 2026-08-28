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
(pending)

## Artifacts
- results/static/smoke1/, results/static/smoke_inv1/ (pipeline validation)
- results/static/phase1_*/results.jsonl (full per-condition rows incl. per-tile SSIMs)

## Conclusion
(pending)
