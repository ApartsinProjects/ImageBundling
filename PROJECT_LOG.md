# PROJECT_LOG

Core setting (anchor): measure whether bundling many small web images into one atlas still
pays off (bytes, load time) under modern codecs (WebP/AVIF/JXL) and protocols (h1/h2/h3),
and map where it stops paying. Plan: ANALYSIS_AND_PLAN.md.

| Date | Experiment | Result | Sanity | Finding |
|---|---|---|---|---|
| 2026-08-28 | Phase 0 scout (scout/PHASE0_SCOUT.md) | Prior art mapped | n/a | No published sprite measurements under h2 or h3; AVIF container floor ~303 B vs JXL 24 B; Cloudinary refuses AVIF under 5,000 px. Planned measurements confirmed novel. |
| 2026-08-28 | smoke1: 8 photos (224px), 5 codecs, atlas vs individual | Pipeline works | Lossless SSIM = 1.0 exactly; lossy SSIM 0.96-0.996 | AVIF atlas saved ~350 B/tile, matching its ~303 B container floor. PNG atlas slightly LARGER than individual (photos don't share PNG filter context). |
| 2026-08-28 | smoke_inv1: atlas-of-1 invariant | PASS | atlas of 1 image byte-identical to single file (jpeg 10986 B, avif 4845 B) | Harness sound. |
| 2026-08-28 | phase1_emoji full sweep (368 rows) | AVIF atlas >=60% saved at n=500, SSIM 0.97; JPEG/JXL ~26%; lossless negative (jxl_ll -35%) | audit clean; invariants pass | Savings scale with container-overhead ratio; lossless atlasing hurts |
| 2026-08-28 | phase1_photos full sweep (368 rows) | AVIF 5.8%, JXL 7.1%, JPEG 3.0%, WebP -8.5% at n=500, SSIM 0.97 | audit clean | 224px tiles gain little; WebP atlasing net-negative on photos |
| 2026-08-28 | audit_negatives (A reproduce, B grid-slack, C identical-copies control, D raw signs) | PASS: all stored rows byte-identical on re-encode; slack negligible; negatives persist raw | positive control: every codec with long-range refs shows 84-99% saving on 100 identical tiles | Negatives real. New insight: cross-image redundancy gain requires LZ/IntraBC-class codecs; intra-only transform codecs (JPEG, lossy WebP) cannot deduplicate distant identical content (1.9-3.4% on identical photos) |
| 2026-08-28 | E3.1 ordering/partition study (Modal, 160 rows) | Ordering worth <=1% for lossy; kmeans chunks +3pp for lossless; photos sorted-order '+18%' traced to 108/500 pixel-identical Picsum duplicates deduped by LZ windows | dup-rate measured by pixel md5; LZ-only signature matches | Similarity ordering does not fix lossy atlas penalty; duplicate exploitation is the real (reframed) win; dedup re-run in flight |
| 2026-08-28 | e31_dedup2 (392 unique photos, Modal) | Ordering ~0%, cluster chunks +0.14% on clean photos | matches LZ-dup hypothesis exactly | Similarity gains on photos were 100% duplicate exploitation; effect real only for duplicate-bearing sets |
| 2026-08-28 | phase2_full network sweep (2647 loads) | SUPERSEDED-BY phase2v2: measurement pages double-fetched every image (JS preload + no-store header defeated coalescing); atlas bytes 2x, individual up to 2x + 250-entry timing-buffer truncation | caught by bytes-vs-manifest check on per-rep data | Timing conclusions void; harness fixed (no-store removed, buffer 4096, bytes invariant), phase2v2 relaunched |

## Bugs found and fixed
- Phase 2 harness: pages fetched each image twice (markup + JS preload) because Cache-Control: no-store blocked request coalescing; fresh-browser-per-load already guarantees cold cache, so no-store removed. Resource-timing buffer raised to 4096 (default 250 truncated byte accounting). Verified: atlas transfers exactly file size, unimodal timings.
- gpu2modal modal_runner autowrap --run built an incomplete argparse.Namespace (missing allow_duplicate/watchdog/fanout fields); patched in the skill and pushed.
- Photo asset set: Picsum seeded URLs return a finite pool; 108/500 tiles pixel-identical. Affects similarity-ordering interpretation; dedup flag added to e31_ordering.
- fetch_assets.sh: Python on Windows emits CRLF; `$(python_gen)` kept trailing `\r` in
  codepoints, corrupting every emoji URL except the last line. Fix: `| tr -d '\r'`.

## Current standing + next
Phase 1 COMPLETE. Byte-level result: bundle small flat lossy assets (AVIF best, >=60%);
do not bundle lossless or 200px+ photos for byte reasons. Results published:
https://apartsinprojects.github.io/ImageBundling/results-phase1.html
Next: Phase 2 network study (Caddy h1/h2/h3 + WSL2 netem + Playwright), where the
per-request overhead question is answered; photos may still win from bundling on timing
even at ~0 byte saving.
