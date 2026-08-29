# Referee report (self-review as journal reviewer), 2026-08-29

Recommendation: MAJOR REVISION. Good, underexplored question; sound matched-quality
method; strong coupling-spectrum synthesis. But headline numbers disagree with the
paper's own tables, empirical base is one icon set + one photo collection, the network
study is underpowered with a visible monotonicity violation, and related work is largely
grey literature.

## Major
- M1. Headline JPEG flat-art "26-34%" contradicts Table 1 (max 26.3% at target 0.97).
  34% must come from a different SSIM target than the abstract states. Figure 1's "24%"
  uses N=100 + equal-settings, an N/protocol absent from Table 1. Reconcile or remove.
- M2. "Both lossless formats lose at N>=200" is refuted by Table 1's photos-56px rows
  (PNG +0.4%, lossless WebP +3.7% at N=200). Scope the claim to flat art.
- M3. Table 2 monotonicity violation: flat-art h2 localhost individual 664ms vs shaped
  100Mbit/20ms 631ms (faster on worse network), breaking the paper's own invariant. No
  CIs (n=7). Report bootstrap CIs, randomized run order; the 1%-loss rows are worst.
- M4. External validity: one Twemoji set + one 521-photo collection. Web-wide rules
  ("~100px break-even", "JPEG always wins") need multiple corpora + randomized
  N-subsampling + bootstrap intervals. Sec 5.4 itself shows content homogeneity flips
  the WebP sign, so one distribution cannot fix the crossover.
- M5. Related work ~half blogs/vendor docs; "first"/"no published measurement" claims
  need a systematic academic search + full records (authors/venue/DOI) for [3][4][14][15].
- M6. Reproducibility: no repo URL, commit, encoder/server/browser versions, or artifact
  DOI, though the text cites a released tool and released data. Hard requirement.

## Moderate
- m7. HTTP/3 result is single server/client/WSL2. Keep the scoped "default deployment can
  under-multiplex" wording; want a second server impl + native Linux. Consolidate the
  HTTP/3 caveat (now split 5.2/6.4) into Limitations.
- m8. "Optimizer" vs "heuristic" toggles (abstract/contrib v vs 6.3). There is no search;
  use "heuristic" throughout.
- m9. 6.1 "no atlas can beat ... for every corpus" is an argument, not a proof; soften or
  state assumptions.

## Minor
- "blast radius" (3.2) informal.
- Figure 1 caption: mark 24% as equal-settings, not Table 1's matched protocol.
- Table 1 missing WebP N=10 flat-art cell: use n/a + footnote (interp out of range).
- 5.2 "15-26% byte saving" lower bound disagrees with Table 1 (WebP flat art N=500 = 8.2%).
- References: full author lists + DOIs; cite published versions of arXiv items.

## Strengths (keep)
Matched-per-tile-SSIM protocol; byte-bundle control; honest negative results; coupling
spectrum + H/C limiting argument; warm-cache Table 4 and HTTP/3 concurrency diagnostic.
