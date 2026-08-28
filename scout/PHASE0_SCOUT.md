# PHASE 0 SCOUT: Prior Art on Image Bundling vs Modern Codecs and Protocols

Date: 2026-08-28. All claims verified via live fetch/search this session unless marked [memory].

## 1. Sprites/bundling vs HTTP/2 multiplexing: published measurements

- **Khan Academy, "Forgo JS packaging? Not so fast" (2015)**: unbundled JS under HTTP/2 performed WORSE than bundles; causes were reduced gzip compression across small files and unexplained server delays serving dozens of files. Conclusion: bundling still wins under HTTP/2. JS-only; no images. [Khan Academy blog](https://blog.khanacademy.org/forgo-js-packaging-not-so-fast/), [Perf Calendar 2015](https://calendar.perfplanet.com/2015/forgo-js-packaging-not-so-fast/)
- **CSS-Tricks, "Musings on HTTP/2 and Bundling"**: 223-icon set, sprited version ~10 KB compressed vs ~115 KB unbundled; concatenation is not an anti-pattern under HTTP/2 (compression-ratio argument, no protocol-level timing matrix). [CSS-Tricks](https://css-tricks.com/musings-on-http2-and-bundling/)
- **USWDS HTTP/2 guidance** recommends against aggressive concatenation under HTTP/2 but without sprite-specific measurements. [designsystem.digital.gov](https://designsystem.digital.gov/performance/http2/)
- Practitioner posts ([pixelfreestudio](https://blog.pixelfreestudio.com/the-pitfalls-of-css-sprites-in-the-age-of-http-2/), [dev.to 2025](https://dev.to/satyam_gupta_0d1ff2152dcc/css-image-sprites-explained-boost-site-performance-in-2025-11gd), [plainenglish.io](https://javascript.plainenglish.io/what-the-heck-happened-to-image-sprites-and-concatenated-assets-794d8633279d)) argue positions in both directions, all without controlled measurements.
- Academic HTTP/2 work exists on page-load and server push ([HTTP/2 Server Push study, arXiv](https://arxiv.org/pdf/2207.05885); [memory] Varvello et al. "Is the Web HTTP/2 Yet?" and Wang et al. "How Speedy is SPDY?" for HTTP/2-vs-1.1 PLT) but none measures image sprites/atlases specifically.
- **No source found quantifying sprites under HTTP/2, and none at all under HTTP/3.**

## 2. Per-file container overhead and small-image codec efficiency

Minimal 1x1-pixel file sizes (proxy for fixed container overhead), from [shkspr.mobi 2024](https://shkspr.mobi/blog/2024/01/whats-the-smallest-file-size-for-a-1-pixel-image/):

| Format | Min 1x1 bytes |
|---|---|
| JPEG XL | 24 |
| WebP | 30 |
| GIF | 35 |
| PNG | 67 |
| ICO | 70 |
| BMP | 126 |
| JPEG | 155 |
| **AVIF** | **303** |

Cross-check: Jon Sneyers, ["One pixel is worth three thousand words" (Cloudinary)](https://cloudinary.com/blog/one_pixel_is_worth_three_thousand_words): GIF 35, PNG 67, JPEG ~160 (141 hand-tuned), lossless WebP 34-38, lossy WebP 44-104, FLIF 15. AVIF's ~300-byte floor comes from mandatory ISOBMFF boxes (ftyp/meta/mdat structure) [memory for mechanism; the number is verified above].

Small-image efficiency claims:
- **Cloudinary's own delivery policy**: images under 5,000 pixels are NOT delivered as AVIF "because the overhead of the file format outweighs the byte-savings"; WebP is used instead. [Cloudinary docs](https://cloudinary.com/documentation/image_optimization)
- The JPEG XL whitepaper highlights deliberately minimized header/metadata overhead "especially important for web delivery of smaller images". [JPEG XL whitepaper PDF](https://ds.jpeg.org/whitepapers/jpeg-xl-whitepaper.pdf)
- 2026 practitioner consensus: AVIF can be larger than JPEG/WebP for thumbnails under ~10 KB; WebP recommended for small images. [minipx](https://minipx.com/blog/webp-vs-avif-vs-jxl/), [usetoolsuite](https://usetoolsuite.com/blog/avif-webp-jpegxl-image-formats-2026/)
- No published systematic sweep of codec efficiency vs tile size (e.g., 16/32/64/128 px) at matched quality was found.

## 3. Browser support status (mid-2026)

| Feature | Status |
|---|---|
| CSS `object-view-box` | Chrome 104+ shipped; Safari: no; Firefox: no (through 157). [caniuse](https://caniuse.com/mdn-css_properties_object-view-box) |
| JPEG XL | Safari: on by default since 2023 (~12% global reach). Chrome 145 (Feb 2026): decoder shipped behind `chrome://flags/#enable-jxl-image-format`, default-on expected H2 2026. Firefox 152 (June 2026): behind a pref. [The Register](https://www.theregister.com/2026/01/14/google_rekindles_relationship_with_jilted/), [fastedit summary](https://fastedit.net/blog/jpeg-xl-browser-support-2026), [jpegxl.info](https://jpegxl.info/resources/software-support.html) |
| 103 Early Hints | Chrome/Edge: yes (preload+preconnect); Firefox 123+ (Feb 2024): preload+preconnect; Safari 17+: preconnect only, no preload. H2/H3 only. [Chrome docs](https://developer.chrome.com/docs/web-platform/early-hints), [MDN](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Status/103) |
| `fetchpriority` | Baseline: Chrome 102+, Safari 17.2 (Dec 2023), Firefox 132 (Oct 2024). [web-features explorer](https://web-platform-dx.github.io/web-features-explorer/features/fetch-priority/) |

Implication: `object-view-box`-based atlas cropping is Chromium-only; cross-browser atlases need CSS background-position or canvas/clip-path fallbacks.

## 4. HTTP/3 vs HTTP/2 under packet loss

- Request Metrics benchmark: HTTP/3 ~55% faster page load on simulated 4G with ~15% loss; ~same as HTTP/2 at 0% loss (where TCP can even win slightly). [requestmetrics.com](https://requestmetrics.com/web-performance/http3-is-fast/)
- Mechanism: QUIC per-stream loss recovery removes transport-level head-of-line blocking that stalls all HTTP/2 streams on one lost packet. [DebugBear](https://www.debugbear.com/blog/http3-vs-http2-performance), [cloudpanel](https://www.cloudpanel.io/blog/http3-vs-http2/)
- Academic: "Measuring HTTP/3: Adoption and Performance" ([arXiv 2102.12358](https://arxiv.org/pdf/2102.12358)) reports nuanced results, roughly parity at high loss in some setups; "Domain-Sharding for Faster HTTP/2 in Lossy Cellular Networks" ([arXiv 1707.05836](https://arxiv.org/pdf/1707.05836)) shows HTTP/2's single connection is fragile under loss, which motivated sharding, the opposite of bundling.
- None of these isolates the many-small-IMAGES workload or compares against an atlas baseline.

## 5. Existing atlas-for-web tools and page-composition stats

- Tools: classic sprite generators exist ([spritegen.website-performance.org](https://spritegen.website-performance.org/); GitHub `sprite-atlas` topic is dominated by game texture atlases). No modern (2023+) tool or paper found doing codec-aware atlasing for web delivery.
- HTTP Archive Web Almanac 2024 Media chapter: median mobile page has 13 `<img>` elements, p90 = 56, max observed 2,174; median image weighs 12 KB; 6.4% of mobile images are 1x1 tracking pixels; format share (mobile): JPEG 32.4%, PNG 28.4%, GIF 16.8%, WebP 12%, SVG 6.4%, AVIF 1.0%. [Almanac 2024 Media](https://almanac.httparchive.org/en/2024/media)
- E-commerce product-grid counts: no published per-grid image-count statistics found. [Gap] The Almanac has an E-commerce chapter [memory], worth a targeted follow-up.

## 6. Chroma-subsampling-safe padding / block alignment

- General guidance verified: pad atlas cells and align to block boundaries; game-engine docs formalize this (Unity `paddingPower`, e.g. 8-px gaps to survive mip levels: [Unity docs](https://docs.unity3d.com/ScriptReference/Sprites.AtlasSettings-paddingPower.html); TexturePacker extrude/padding: [codeandweb](https://www.codeandweb.com/texturepacker/documentation/texture-settings)); edge-extrusion ("bleed") technique: [bugnet.io](https://bugnet.io/blog/how-to-fix-texture-bleeding-and-seams-in-an-atlas).
- 4:2:0 subsampling causing color bleeding across sharp edges: [Wikipedia chroma subsampling](https://en.wikipedia.org/wiki/Chroma_subsampling).
- **No authoritative published source found on codec-block-aligned sprite placement for web atlases specifically** (JPEG 16-px MCU with 4:2:0, AVIF 64/128-px superblocks). The block-size facts themselves are standard [memory: JPEG MCU = 16x16 at 4:2:0; AV1 superblocks 64x64/128x128], but their application to sprite padding appears unpublished.

## What would be novel

1. **Bytes-saved-by-atlasing per codec x tile-size at matched quality**: not published. Only endpoints exist (1x1 overhead floors; Cloudinary's <5,000-pixel AVIF cutoff). No one has swept N tiles x tile-size x {JPEG, PNG, WebP, AVIF, JXL} with matched-quality controls (SSIMULACRA2/butteraugli) comparing sum-of-files vs atlas.
2. **Crossover map (N x tile-size x RTT x protocol)**: not published. All sprite-vs-multiplexing measurements predate HTTP/3 and mostly predate HTTP/2 deployment maturity; the JS-bundling result (Khan Academy) is the closest and is 2015, JS-only. Nothing quantifies where atlasing stops paying under H2 or H3, or under loss.
3. **Chunked-atlas middle ground** (k atlases of m tiles balancing cache granularity, loss blast-radius, and overhead amortization): no prior work found at all.
4. **Codec-block-aligned sprite padding rules for web atlases** (16-px JPEG MCU, AVIF superblock alignment) with measured artifact/size impact: unpublished; game-engine padding lore is GPU-sampling-motivated, not codec-motivated.
5. Interaction of atlasing with `object-view-box` (Chromium-only) vs `background-position` and with `fetchpriority`/Early Hints: no measurements found.
