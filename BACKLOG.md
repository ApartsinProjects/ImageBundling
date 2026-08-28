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

## P1b: method upgrades to widen savings across all codecs (added 2026-08-28)
- E3.6 Byte-bundle condition: concatenate the N individually-encoded files into ONE
  binary resource + JSON index; client slices the ArrayBuffer and decodes each via
  createImageBitmap/blob. Keeps per-image codec adaptation (no shared-model penalty,
  no quality coupling) while still collapsing N requests into 1. By construction its
  bytes equal the individual condition minus nothing; it can never lose bytes and
  still wins latency. The right baseline-beater for WebP-on-photos and all lossless
  content. Add as a condition to the network study pages.
- E3.7 Layout variants: vertical-strip atlas (1 tile per scanline row-band) should
  recover PNG's per-scanline filter adaptation (PNG negative may flip positive);
  16px-aligned cell sizes (72->80) stop DCT blocks straddling tiles for JPEG/WebP;
  2D similarity placement (Hilbert-order clusters) matches AVIF superblock-local
  adaptation better than 1D row-major order.
- E3.8 Encoder-side spatial adaptivity inside one atlas: libaom delta-q / ROI maps
  (avifenc/aom --deltaq-mode) to restore per-region quantization that atlasing takes
  away; JPEG XL patches for repeated elements in icon sets.
- E3.9 Cross-file dictionary compression as another bundling axis: tar of PNGs +
  Brotli/zstd (shared window across files) vs PNG atlas vs individual PNGs.
- E3.10 Atlas-tuned encoder configs (fair under matched-quality): AVIF via avifenc/aom
  screen-content tools (--enable-intrabc, palette) for flat atlases + deltaq/ROI maps;
  JXL smaller modular group size (128px groups restore per-region tree/palette
  adaptation, direct fix candidate for the jxl_ll -44%) + patches; PNG strip layout +
  sorted order (E3.1 shows sorted photo order +18%, VERIFY first); WebP max partitions.
- E3.11 Trained shared dictionaries: (a) Compression Dictionary Transport
  (Use-As-Dictionary, shipped in Chrome): serve updated atlas delta-compressed against
  the cached previous atlas -> cache-invalidation blast radius collapses to the delta;
  (b) zstd dictionary trained on the tile-file corpus for byte-bundles; (c) trained-
  codebook texture codecs (Basis Universal) for the WebGL path.
- E3.1 follow-up: verify the PNG+sorted-photos +18% locally (re-encode independently,
  compare against individual files); if real, PNG atlasing flips positive with a
  packing rule, no format change.

## P2
- Phase 3 original items: display-mechanism timing comparison, decoded-memory profile,
  lazy-loading vs atlas below-the-fold, bleed/padding quality study (needs a
  block-artifact-sensitive metric, SSIM under-weights chroma bleed).
- Butteraugli/SSIMULACRA2 secondary quality metric to harden matched-quality claims.
- DOCX build of the paper (html2doc, house profile) once Phase 2 results are in.

## Priority log
- 2026-08-28: created; P1 added at user request (optimal atlas selection/partition).
