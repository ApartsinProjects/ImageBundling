# Image Bundling: Analysis and Measurement Plan

Date: 2026-08-28. Status: planning, no experiments run yet.

## 1. The idea

Many web pages load dozens to hundreds of small images: product thumbnails, icons, avatars,
decorative elements. Each one paid for separately costs:

1. **Per-request overhead**: request/response headers, server-side lookup, browser scheduling,
   and (on HTTP/1.1) connection limits and head-of-line blocking.
2. **Per-file compression overhead**: every image file carries fixed container cost
   (JPEG headers and quantization tables, roughly 0.3-0.8 KB; PNG chunk structure; AVIF/HEIF
   box structure, often 0.3-1 KB). For a 2 KB icon this is a 15-40% tax.
3. **Lost cross-image redundancy**: codecs exploit redundancy only inside one file. A hundred
   icons sharing a palette and style compress far better as one image than as one hundred.

The proposal: pack many small images into one large mosaic (an atlas), serve it as a single
resource, and display each region client-side with browser primitives. This is the classic
CSS-sprites technique, revisited under modern codecs (WebP, AVIF, JPEG XL) and modern
protocols (HTTP/2, HTTP/3) which were supposed to have made it obsolete. The question this
project answers empirically: **how much does bundling still save, for which image types,
sizes, counts, codecs, and protocols, and when does it hurt?**

### Display mechanisms available in browsers

| Mechanism | Notes |
|---|---|
| CSS `background-position` + `background-size` | The classic sprite method; works everywhere. |
| CSS `object-view-box` on `<img>` | Modern, purpose-built cropping of one source into many `<img>` elements; Chromium-only today. |
| `<canvas>` `drawImage(src, sx, sy, sw, sh, ...)` | Full control; one decode, many blits; costs JS and canvas memory. |
| SVG `<image>` + `viewBox` / `clip-path` | Declarative crop; works in `<img>`-like contexts. |
| WebGL/WebGPU texture atlas | For app-like UIs; out of scope for the core study, note as extension. |

### Expected pros (hypotheses to test)

- H1: For N small images, total bytes(atlas) < sum of bytes(individual) at matched visual
  quality, with the gap growing as tile size shrinks and N grows, and largest for
  stylistically homogeneous sets (icon packs).
- H2: Time-to-all-images-visible improves most on HTTP/1.1 and on high-RTT networks; the gap
  narrows but does not vanish on HTTP/2/3 (header compression and multiplexing reduce, not
  eliminate, per-request cost; server think-time and browser scheduling remain per-request).
- H3: Decode cost: one large decode beats N small decodes in total CPU, but raises peak
  memory (decoded atlas is W*H*4 bytes regardless of encoded size) and can delay
  first-image-visible relative to progressive individual loading.

### Expected cons and risks (also measured, kept in the registry)

- **Cache granularity**: changing one tile invalidates the whole atlas. Quantify re-download
  cost under realistic update rates.
- **All-or-nothing latency**: nothing renders until the atlas arrives; individual images
  render incrementally. LCP can move either way.
- **Lossy bleed at tile borders**: chroma subsampling and block transforms smear neighboring
  tiles into each other. Mitigation: pad tiles and align to codec block grid (8 px for JPEG,
  16 px safe for WebP, 64 px superblock-safe for AVIF); measure the padding tax.
- **Decoded memory blow-up**: a 4096x4096 atlas is 64 MB decoded even if 300 KB on the wire.
  Matters on mobile; measure.
- **Wasted pixels**: below-the-fold or never-shown tiles are still downloaded and decoded.
  Compare against lazy-loaded individual images.

## 2. Factors and levels

| Factor | Levels |
|---|---|
| Image class | flat icons (16-64 px), photo thumbnails (100-300 px), decorative/UI chrome (mixed), emoji/avatar (32-128 px) |
| Count N | 10, 50, 200, 500 |
| Codec | PNG (lossless), mozjpeg, WebP lossy, WebP lossless, AVIF, JPEG XL (Safari-class support), plus SVG-sprite baseline for vector icons |
| Bundling | individual files, single atlas, chunked atlases (e.g., 4 atlases of N/4, the middle ground) |
| Packing | uniform grid vs. shelf/MaxRects; block-aligned padding 0/8/16/64 px |
| Protocol | HTTP/1.1 (keep-alive, 6 connections), HTTP/2, HTTP/3 (QUIC) |
| Serving extras | baseline, `<link rel=preload>`, 103 Early Hints, `fetchpriority`, `loading=lazy` (individual only), Brotli/zstd for the HTML/CSS side |
| Network profile | localhost (overhead floor), fast broadband (100 Mbps / 20 ms), 4G (9 Mbps / 60 ms), slow 3G-class (1.6 Mbps / 150 ms), each also with 1% loss variant (loss is where HTTP/3 should differentiate) |
| Display mechanism | background-position, object-view-box, canvas (fixed to background-position for the main grid; mechanism compared in one dedicated sub-experiment) |

The full cross is too large. Design: (a) a **static compression study** over
class x N x codec x packing with no network at all; (b) a **network study** over
protocol x network x bundling x N using one or two representative codecs chosen from (a);
(c) targeted sub-experiments (display mechanism, cache invalidation, memory).

## 3. Metrics

All co-computed per run on one config and saved as one artifact per run
(JSON: config + all metrics), per the one-pass comparison rule.

**Bytes**: encoded bytes on the wire (per resource and total, from server logs, so
header bytes are included), request count.

**Quality (static study)**: per-tile SSIM and butteraugli distance computed after extracting
the tile back out of the decoded atlas (this captures border bleed, not just codec quality).
Size comparisons only at matched per-tile quality (rate-distortion curves, compare bytes at
fixed butteraugli target).

**Timing (network study)**, via Playwright + Chrome DevTools Protocol traces:
- TTFB, time-to-first-image-painted, time-to-all-images-painted (the primary endpoint),
  LCP, total page load.
- Decode time summed from Chrome `ImageDecodeTask` trace events.

**Resources**: peak renderer memory (CDP `Performance.getMetrics`), CPU time from traces.

Each cell runs >= 15 page loads, cold cache, report median and IQR; paired comparisons
(bundled vs. unbundled on the same seed/config) with bootstrap CIs.

## 4. Testbed

- **Assets**: real icon packs (e.g., an open-source icon set rasterized), product-photo
  thumbnails from an open dataset, generated decorative elements. Deterministic manifest
  (list of tiles + sizes + seed) so every condition uses the same pixels.
- **Pipeline** (Python 3.14 + Pillow for orchestration, external encoders: `cwebp`,
  `avifenc`, `cjxl`, `mozjpeg`, `oxipng`): manifest -> pack -> encode at a quality ladder ->
  measure -> emit atlas + CSS/JSON coordinate map + generated test page.
- **Server**: Caddy (single binary, serves h1/h2/h3 with one config) on localhost;
  self-signed cert with Chrome flags to trust it (h2/h3 require TLS).
- **Network shaping**: run server inside WSL2 and shape with `tc netem`
  (delay/bandwidth/loss applied to real packets, so it is protocol-faithful, which
  browser-level DevTools throttling is not, especially for QUIC/UDP).
- **Client**: Playwright-driven Chromium, cold profile per load, trace capture on.

**Invariants stated in advance** (per the verify-before-reporting rule):
- An atlas containing exactly 1 image must be within a few hundred bytes of the individual
  file, and identical in timing to within noise.
- Localhost, N=10, h2: bundled vs. unbundled must differ by nearly nothing (overhead floor
  sanity check).
- Sum of per-resource bytes from server logs must equal bytes measured at the client.
- More network impairment must never make any condition faster.
- h1 with 500 individual images must be clearly the worst timing cell; if it is not, the
  harness is broken.

## 5. Phases

- **Phase 0, scout** (skill: `web-researcher` / `deep-research`): prior art on sprites vs.
  HTTP/2 (published measurements exist and set expectations), codec container overhead
  numbers, `object-view-box` support status, HTTP/3 loss-recovery measurements. Deliverable:
  short annotated source list; establishes which results would be novel.
  Agent time: ~15-30 min.
- **Phase 1, static compression study**: build asset pipeline, run class x N x codec x
  packing, produce rate-distortion and overhead curves. Answers H1 and the padding-tax
  question with zero networking. Agent time: ~1-2 h including pipeline debugging; compute
  is local CPU, minutes.
- **Phase 2, network study**: testbed bring-up (Caddy + WSL2 netem + Playwright harness),
  smoke test on 2 cells, then protocol x network x bundling x N with the Phase 1 winning
  codec per class. Agent time: ~2-4 h bring-up and smoke; the full sweep is
  (3 protocols x 5 networks x 3 bundling x 4 N x 15 loads) ~ 2,700 loads, roughly 3-6 h
  unattended local wall-clock, $0.
- **Phase 3, targeted sub-experiments**: display-mechanism comparison, cache-invalidation
  cost model (tile update rate sweep), decoded-memory profile, lazy-loading vs. atlas for
  below-the-fold content. Agent time: ~1-2 h each, run only the ones Phase 2 makes
  interesting.
- **Phase 4, synthesis**: decision chart ("bundle when: image class X, N >= Y, protocol Z,
  network W") backed by the measured deltas; optionally a small JS/CLI tool that takes a
  directory of images and emits atlas + CSS map as the practical artifact.

Phases 1-3 run as `auto-research` cycles: hypothesis stated first, experiment registry for
every run including nulls, PROJECT_LOG maintained, sanity invariants checked before any
number is reported.

## 6. What would make the result interesting

The known story is "sprites help on h1, h2 made them pointless". The potentially novel,
measurable claims are:
1. The **compression-sharing win** (H1) is protocol-independent and survives h3; nobody
   quantifies it per codec x tile-size, and AVIF/JXL container overhead makes it larger
   than in the JPEG era, not smaller.
2. A **crossover map**: the (N, tile size, RTT) surface where bundling stops paying,
   per protocol.
3. The **chunked-atlas middle ground** (a few bundles instead of one) may dominate both
   extremes: most of the byte savings, bounded cache-invalidation and memory cost.

## 7. Phase 3 extension: optimal atlas partitioning (added 2026-08-28)

Beyond the binary bundle-or-not decision, choose the partition of an image set into
atlases that minimizes a weighted cost J combining (a) expected bytes per deploy under
per-image update rates (whole-bundle invalidation), (b) load latency for the target
protocol and network (parallelism vs request overhead), and (c) peak decoded memory,
subject to a per-tile quality floor. Measured inputs: similarity-aware grouping effect
(E3.1), J(k) chunk-count curves (E3.2), cadence-grouped partitions (E3.3), mixed-size
packing (E3.4). Deliverable: an atlas-optimizer CLI that emits partition + per-bundle
codec + atlas files + CSS map from a directory and a manifest (E3.5). Details: BACKLOG.md.
