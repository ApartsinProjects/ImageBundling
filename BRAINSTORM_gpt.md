# ChatGPT consult: making JPEG/PNG/WebP win at atlasing (2026-08-29)

Via GPTConsult (ChatGPT, High effort, brief attached). Verbatim, lightly de-noised.

---

The brief’s central diagnosis is correct: atlas gains come from amortizing fixed costs, while losses come from forcing unrelated tiles to share adaptive codec state. Your measurements already isolate this unusually well, especially the PNG strip result and the WebP autofilter reversal. 
My ranking of the next three experiments is:

Priority	Technique	Case attacked	Expected change in atlas-vs-individual gap
1	VP8L entropy-image / histogram-group control	lossless WebP photos, currently −2 to −5%	+2 to +6 percentage points
2	PNG vertical strip + explicit tile-boundary filter reset + tile-aligned DEFLATE blocks	PNG photos, currently ~0% strip	+0.5 to +3 pp
3	Corpus-trained JPEG tables experiment, mainly as a definitive negative result	JPEG shared-table question	probably −1 to +1 pp vs plain optimized atlas

These correspond directly to the three unresolved codec-specific questions in the brief. 
1. Lossless WebP: attack the entropy image, not the ordinary CLI knobs

This is the experiment I would do first.

VP8L is much less globally coupled than the brief perhaps implies. The lossless bitstream supports spatially varying prefix-code groups, represented through the entropy/meta-prefix image. Different regions can therefore use different Huffman codes. In principle this is exactly what an atlas of heterogeneous photos needs.

The problem is that cwebp does not expose the important partitioning parameters directly. Standard:

cwebp -lossless -m 6 -q 100 input.png -o out.webp

already enables aggressive histogram analysis, but libwebp is choosing the histogram partitioning and clustering itself.

I would patch/instrument libwebp and sweep:

entropy/histogram tile size, usually represented internally via histogram bits

number/aggressiveness of histogram clusters

color-cache bits

cache disabled versus enabled

potentially predictor-transform block size if accessible in the encoder path

The important VP8L bitstream features are:

predictor transform

subtract-green transform

color transform

color indexing transform

LZ77 backward references

color cache

multiple Huffman/meta-prefix groups selected spatially

Experiment

Take your 112px and 224px diverse-photo sets.

Use a simple vertical or near-square atlas, but make tile boundaries align with candidate entropy-grid sizes. Sweep approximate spatial group sizes:

16×16
32×32
64×64
128×128

and force/instrument histogram partitioning rather than letting libwebp collapse heterogeneous regions into shared clusters.

Also sweep color-cache sizes equivalent to roughly:

0, 4, 6, 8 cache bits

where supported internally.

The key comparison is not absolute compression. Measure:

atlas_custom / sum(individual_custom)

using the same modified encoder on both sides.

Why this could flip −2…−5%

Suppose tile A is foliage, tile B is skin, tile C is sky, tile D is textured fabric. A single merged symbol distribution is exactly what hurts the atlas.

If VP8L maintains different entropy groups for those regions, you recover much of the individual-image entropy specialization while still retaining:

one RIFF/WebP container

one image header

cross-tile LZ opportunities

shared transformations where useful

My plausible target is:

current:       −2% … −5%
after tuning:  −1% … +2%
best cases:          +3%

I would consider +2 to +6 percentage points of gap recovery realistic enough to justify the experiment.

Near-lossless

Separately test:

cwebp -lossless -near_lossless 100 -m 6
cwebp -lossless -near_lossless 95  -m 6
cwebp -lossless -near_lossless 90  -m 6
cwebp -lossless -near_lossless 80  -m 6

and binary-search to SSIM 0.97.

Near-lossless can reduce photographic entropy substantially, but the meaningful question is whether it disproportionately helps the atlas. I would expect perhaps another 1–3 pp improvement in relative atlas efficiency, not the much larger absolute size reduction you may see.

Novelty: forcing the VP8L entropy-image geometry specifically to coincide with atlas tile structure is reasonably novel as an atlas optimization. Trying -m 6, -q, and -near_lossless is standard.

2. PNG: retain your vertical strip, but give DEFLATE approximately per-tile entropy adaptation

Your result

grid −3…−6%; vertical strip +9% for flat art; diverse photos strip ~parity

is highly diagnostic. 
For photographs I think the vertical strip is essentially the correct spatial layout. I would stop trying clever 2-D packing.

The remaining opportunity is below the PNG filter layer: DEFLATE block construction.

A. Explicitly reset the PNG predictor at tile boundaries

For a vertical atlas, force the first scanline of every tile to use:

Filter 0: None

or test:

Filter 0: None
Filter 1: Sub

Do not allow Up, Average, or Paeth on that first scanline, because their previous-row reference belongs to the preceding unrelated tile.

After that first row, return to normal exhaustive/adaptive filter selection.

Cheap experiment:

tile row 0: force None
tile rows 1..H-1: normal minimum-cost filter

versus your current encoder.

I expect only 0.1–0.8%, because a good PNG filter heuristic probably already avoids catastrophically bad boundary predictions. But it costs almost nothing to test.

B. Much more interesting: force DEFLATE block boundaries near tile boundaries

PNG's concatenated IDAT chunks still form one zlib/DEFLATE stream, so simply making one IDAT per tile does nothing.

Instead, deliberately terminate the current DEFLATE block after each tile while preserving the LZ dictionary.

Conceptually you want:

tile 1 filtered bytes
dynamic Huffman block boundary
tile 2 filtered bytes
dynamic Huffman block boundary
tile 3 ...

but not a full dictionary flush.

With zlib, investigate a Z_BLOCK-style boundary rather than Z_FULL_FLUSH.

The point is:

each photo can obtain a new dynamic Huffman tree;

the 32 KiB history can remain available;

you keep one PNG container and one zlib wrapper.

This is almost exactly the missing middle point between:

one globally compressed atlas

and

N completely independent PNG streams
Expected gain

For 112–224px photos I would expect something like:

strip today:          −0.5 … +0.5%
forced filter reset:       +0.2 … +0.7 pp
tile-aware DEFLATE:        +0.5 … +2.5 pp

So a realistic successful result is perhaps +1–2% atlas advantage, occasionally +3%.

There is an optimum grouping size. One Huffman tree per tiny 56px image may cost too much. Test:

1 tile / DEFLATE block
2 tiles / block
4 tiles / block
8 tiles / block
automatic zlib

For 224px photographs, 1–2 tiles/block is more plausible; for 56px images, probably several tiles/block.

What probably will NOT help

I would not spend much more time on:

Adam7 interlacing

multiple IDAT chunks

serpentine layouts

separator columns/large gutters

a single shared indexed palette for diverse photos

A single PNG PLTE is global, so for heterogeneous photography it recreates exactly the adaptive-state problem you are trying to eliminate. Your spectacular +90–97% shared-palette result is therefore a special property of limited-color icon corpora, not a general photo technique. 
Novelty: tile-aligned DEFLATE block formation while deliberately retaining cross-tile dictionary history is the interesting research contribution. PNG filter-reset rows are standard engineering.

3. JPEG: I expect the proposed shared-table per-tile scheme not to beat a well-optimized atlas

This is the case where I would run a relatively small experiment and then close the question.

You already find that JPEG's atlas advantage is overwhelmingly the roughly 600 B/image table/header amortization. 
A plain JPEG atlas already gets the main benefit:

one SOI
one frame
one set of DQT
one/few DHT sets
one EOI

The proposed scheme:

separately encoded tiles + common optimized DQT/DHT tables

can retain individual entropy streams, but it cannot magically eliminate their structural overhead while remaining an ordinary single browser-decodable baseline JPEG image.

More importantly, standard baseline JPEG does not provide arbitrary spatial quantization tables per tile inside one frame.

Quantization tables are selected by component, not MCU region.

So you cannot simply say:

tile A: Q=71
tile B: Q=82
tile C: Q=65

inside an otherwise normal baseline JPEG atlas.

Restart markers:

DRI
RST0 ... RST7

can reset entropy/DC state at MCU intervals, but they do not provide per-region quantization.

Corpus-trained tables are still worth one definitive experiment

Train a common table set on the complete corpus and encode:

individual images using that common DQT/DHT set;

one atlas using exactly the same set;

normal individually optimized images;

normal whole-atlas optimized JPEG.

With mozjpeg, use the strongest ordinary baseline/progressive configurations you actually intend to serve, e.g. variations around:

cjpeg -optimize ...

plus trellis optimization where enabled, and separately test progressive mode if your web-performance experiment permits it.

The crucial experimental matrix is:

                    per-image tables    corpus tables
individual files          A                  B
atlas                     C                  D

I predict:

B < A only slightly, or B > A
D ≈ C

and therefore the pooled-table tile bundle will not materially exceed the normal atlas.

Likely effect relative to your optimized plain atlas:

−1% … +1%

Perhaps +1–2% in a very homogeneous corpus, but not enough to constitute a new general technique.

Your earlier result that abbreviated/shared-table JPEG was approximately equal to a plain JPEG atlas is already strong evidence in this direction. 
Novelty: corpus-trained quantization/Huffman tables are established JPEG practice. Applying them as the controlled comparison here is scientifically useful, but I would not expect a new compression result.

Can every codec be made to win for every realistic image class?

I think the answer is no, if the requirement is:

one ordinary pixel image, decodable by browsers as JPEG/PNG/WebP, smaller than independently optimized files for every heterogeneous corpus.

There is a fairly fundamental reason.

For N images, individual serving costs sum_i (H_i + C_i(x_i)), where H_i is the
per-file fixed overhead and C_i is compression using state optimized for image i.
An atlas costs roughly H + C(x_1..x_N; theta) with one shared header and one shared
adaptive state theta. The atlas wins when the saved overhead (sum_i H_i - H) exceeds
the cost of replacing each image's optimal state theta_i with shared state theta. For
large, unrelated photographs H_i/C_i -> 0: there is essentially no fixed overhead left
to amortize, while even a small adaptation penalty remains. That is exactly why the
So I would formulate the research conclusion not as:

find one atlas construction that always wins.

but rather:

determine how much codec adaptation can be spatially decoupled while retaining single-resource amortization.

That leads to a useful hierarchy:

JPEG
mostly globally coupled quantization
→ atlas naturally wins mainly through large fixed-header savings

PNG
filter adaptation is scanline-local
DEFLATE adaptation can be block-local
→ strip + tile-aware DEFLATE may approach the ideal compromise

VP8L
explicit spatial entropy groups already exist
→ strongest unexplored opportunity for genuinely tile-aware atlasing

byte-bundle
fully independent codec state
→ theoretical escape hatch when adaptive-state loss exceeds fixed-cost savings

Your byte-bundle result is therefore not merely an implementation workaround. It is effectively the zero-coupling endpoint of the coupling spectrum you describe. 
The three experiments I would actually run next

Patch libwebp VP8L to control entropy/histogram spatial partitioning. Sweep histogram-group scale and color-cache settings, aligned to atlas tiles. This has the highest probability of turning the current −2…−5% photo result positive.

Build a custom PNG strip encoder with tile-boundary filter resets and DEFLATE block boundaries without dictionary reset. Sweep 1/2/4/8 tiles per dynamic block. A stable +1–2% on diverse photos would already be a meaningful result.

Run the common-table JPEG 2×2 experiment and probably close the branch. If corpus-trained DQT/DHT cannot beat the optimized whole atlas by at least ~1%, there is little reason to pursue per-tile JPEG scans further; baseline JPEG lacks the spatial quantization freedom needed for the proposed ideal construction.