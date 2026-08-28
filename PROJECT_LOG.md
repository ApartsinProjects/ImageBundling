# PROJECT_LOG

Core setting (anchor): measure whether bundling many small web images into one atlas still
pays off (bytes, load time) under modern codecs (WebP/AVIF/JXL) and protocols (h1/h2/h3),
and map where it stops paying. Plan: ANALYSIS_AND_PLAN.md.

| Date | Experiment | Result | Sanity | Finding |
|---|---|---|---|---|
| 2026-08-28 | Phase 0 scout (scout/PHASE0_SCOUT.md) | Prior art mapped | n/a | No published sprite measurements under h2 or h3; AVIF container floor ~303 B vs JXL 24 B; Cloudinary refuses AVIF under 5,000 px. Planned measurements confirmed novel. |
| 2026-08-28 | smoke1: 8 photos (224px), 5 codecs, atlas vs individual | Pipeline works | Lossless SSIM = 1.0 exactly; lossy SSIM 0.96-0.996 | AVIF atlas saved ~350 B/tile, matching its ~303 B container floor. PNG atlas slightly LARGER than individual (photos don't share PNG filter context). |
| 2026-08-28 | smoke_inv1: atlas-of-1 invariant | PASS | atlas of 1 image byte-identical to single file (jpeg 10986 B, avif 4845 B) | Harness sound. |

## Bugs found and fixed
- fetch_assets.sh: Python on Windows emits CRLF; `$(python_gen)` kept trailing `\r` in
  codepoints, corrupting every emoji URL except the last line. Fix: `| tr -d '\r'`.

## Current standing + next
Phase 1 pipeline validated by smoke test. Assets downloading (520 emoji + 520 photos).
Next: full Phase 1 sweep (2 classes x N in {10,50,200,500} x 5 codec families x quality
ladder x padding {0,8,16}), then aggregate bytes-at-matched-SSIM.
