# Phase 2: network timing study (h1/h2/h3 x shaped profiles x serving condition)

Status: completed (tag phase2v3). Supersedes phase2_full (double-fetch harness bug).

## Hypothesis
H2: time-to-all-visible improves most on HTTP/1.1 and high-RTT networks; the gap
narrows but does not vanish on HTTP/2/3.

## Setup
Caddy in WSL2 (h1-only :8441, h2 :8442, h3 :8443, tls internal); tc netem egress
shaping; Playwright Chromium, fresh browser per load (cold TCP/QUIC + cache); page
stamps performance.now() after all tiles decoded + 2 rAFs; per-resource protocol and
transferSize recorded and validated (protocol must match endpoint; bytes must match
manifest). Assets WebP q80. Conditions: individual, atlas1, atlas4, bundlebin (concat
of individual files + offset index, client-side blob slicing + decode). N in
{50,200,500} (n=10 dropped mid-run, no effect observed), classes emoji/photos,
profiles localhost / 100Mbit-20ms / 9Mbit-60ms / 9Mbit-60ms-1%loss (slow3g dropped
mid-run to cut wall-clock; cell4g covers the pattern). Reps 8 (localhost, fast) or 5
(cell4g, lossy4g), first rep dropped. 2,515 validated loads, 0 errors, 0 protocol
mismatches.

## Headline numbers (N=500, median, speedup vs individual)
| profile | proto | flat: atlas | flat: bundle | photos: atlas | photos: bundle |
|---|---|---|---|---|---|
| localhost | h1 | 8.3x | 2.5x | 2.0x | 1.2x |
| fast | h1 | 9.0x | 4.4x | 2.6x | 1.9x |
| fast | h2 | 2.7x | 1.2x | 0.9x | 0.7x |
| fast | h3 | 7.9x | 3.6x | 2.8x | 2.1x |
| cell4g | h2 | 1.1x | 0.8x | 1.0x | 0.9x |
| cell4g | h3 | 5.7x | 3.9x | 1.6x | 1.4x |
| lossy4g | h1 | 7.1x | 3.3x | 0.9x (atlas4: 1.8x) | 0.9x |
| lossy4g | h3 | 5.0x | 3.2x | 1.3x | 1.2x |

## Findings
1. H2 confirmed for h1 and, unexpectedly, h3: 4-9x atlas speedups persist. HTTP/2 is
   the exception: multiplexing loads 500 small files near atlas speed on shaped links,
   so bundling under pure h2 is chiefly a byte play.
2. h3 individual-file loads are 4-5x slower than h2's on the same links (consistent
   with tighter QUIC concurrent-stream budgets); h3 fleets inherit h1-like bundling
   economics.
3. Chunked atlas is loss insurance: lossy h1 photos atlas1 0.9x vs atlas4 1.8x
   (single-connection stall risk); chunking otherwise costs ~nothing.
4. Byte-bundle beats individual serving nearly everywhere on h1/h3 (up to 5.7x) at
   identical bytes; the right bundle type for photos/lossless content.

## Audit
Superseded run phase2_full carried a double-fetch bug (JS preload + no-store defeated
coalescing; atlas bytes exactly 2x file size) caught by per-rep bytes inspection
before publication; harness now validates bytes per load. phase2v3 invariants: atlas
transfer = file size + headers; localhost N=50 h2 bundling effect ~0; impairment never
speeds any condition; h1-individual-500 worst or near-worst timing cell per profile.

## Artifacts
results/network/phase2v3/{loads.jsonl, summary.json}; superseded:
results/network/phase2_full/.
