# BACKLOG

## P0: Phase 2 completion
- Aggregate phase2_full, add network results section + figures to paper, publish.

## P1: Phase 3, optimal atlas partitioning (user-requested extension)
Frame: given images i with size s_i, class c_i, lossless flag, update rate p_i, and
visibility v_i, choose a partition into bundles B_1..B_k and a codec per bundle to
minimize J = w_b * E[bytes per deploy] + w_t * latency(k, protocol, network) +
w_m * peak decoded memory, subject to quality >= target.

- E3.1 Similarity-aware grouping: does clustering visually similar tiles into the same
  atlas beat random assignment on bytes at matched SSIM? Strategies: random, sorted by
  mean color, k-means on color histogram, k-means on tiny-embedding. Codecs: AVIF, WebP,
  JPEG. Hypothesis: cross-tile context sharing improves when neighbors are similar;
  effect largest for lossless and low-quality lossy. Cheap: reuses static_study harness
  with a `--order` option.
- E3.2 Optimal chunk count k: sweep k in {1,2,4,8,16,32} x N x class. Bytes side from
  static harness (overhead amortization loss as k grows); latency side from network
  harness (parallelism gain as k grows, esp. h1 6-connection regime and lossy profiles).
  Output: measured J(k) curves; expected-transfer-per-deploy model
  E[bytes] = sum_j [1 - prod_{i in B_j}(1 - p_i)] * bytes(B_j) validated against the
  curves; closed-form guidance for k*(N, tile size, update rate).
- E3.3 Update-cadence-aware partitioning: two-cadence synthetic workload (stable icons +
  weekly seasonal set); compare cadence-grouped vs mixed partitions on E[bytes] over
  simulated deploy sequences.
- E3.4 Mixed-size packing: heterogeneous tile sizes (16-256 px); grid vs shelf vs
  MaxRects; wasted-pixel cost vs savings; interaction with codec block sizes.
- E3.5 The artifact: `atlas-optimizer` CLI. Input: directory + manifest (update rates,
  quality target, memory cap, protocol). Output: partition, per-bundle codec, atlas
  files + CSS map. Cost model calibrated from E3.1-E3.4 measured curves. Greedy:
  cadence-partition first, similarity-cluster within cadence, then k chosen by J(k).

## P2
- Phase 3 original items: display-mechanism timing comparison, decoded-memory profile,
  lazy-loading vs atlas below-the-fold, bleed/padding quality study (needs a
  block-artifact-sensitive metric, SSIM under-weights chroma bleed).
- Butteraugli/SSIMULACRA2 secondary quality metric to harden matched-quality claims.
- DOCX build of the paper (html2doc, house profile) once Phase 2 results are in.

## Priority log
- 2026-08-28: created; P1 added at user request (optimal atlas selection/partition).
