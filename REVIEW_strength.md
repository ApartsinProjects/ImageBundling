1. RELATED WORK
Verdict: needs expansion before SPE submission

The current Section 2 is coherent but too compact for an archival journal. It has only four short subsections and 32 references, with a substantial fraction being specifications, documentation, blogs, or practitioner material. That is acceptable in an SPE paper, but the academic spine is still thin: essentially Marx et al. is the closest direct bundling paper, WProf/SPDY/Polaris provide broader loading context, and Barman–Martini provides the main modern codec paper. 

paper(20260829-072146) +1

I would not regard this as a blocking weakness, but I would expect an SPE reviewer to request a more systematic related-work treatment. Roughly 10–15 well-chosen additional references, plus some restructuring, would be sufficient.

A. Web resource bundling, aggregation, and packaging — Section 2.1 is still thin

You correctly cover CSS sprites, inlining, JS/CSS concatenation, and Marx et al., and distinguish request reduction from byte-level compression. 

paper(20260829-072146)

 But the paper needs a better lineage from generic page-resource aggregation to your image-specific contribution.

I would add:

Butkiewicz, Madhyastha & Sekar, “Understanding Website Complexity: Measurements, Metrics, and Implications,” ACM IMC 2011. Useful background showing the increasing number and heterogeneity of page resources. It strengthens the motivation for treating many-small-resource loading as a systems problem.

Steve Souders, High Performance Web Sites (2007) and/or Even Faster Web Sites (2009). Not archival papers, but canonical sources for sprites, request aggregation, concatenation, and HTTP/1-era practice. For an SPE paper about revisiting an engineering practice, this lineage is relevant.

The Web Bundles / Web Packaging standards effort should at least be discussed as a conceptual relative: packaging many logical resources into a transport object while preserving resource identity is much closer to your byte-bundle than ordinary CSS spriting. Explicitly explain why your byte-bundle is experimentally different.

Modern build-tool practice: webpack asset modules/url-loader, Vite's asset inlining threshold, Parcel, etc. These are practitioner references, but SPE specifically values the bridge from empirical result to software practice.

The missing comparison is not “someone already did image atlasing”; it is that the paper currently makes the surrounding resource-packaging design space look smaller than it actually is.

B. HTTP/2 and HTTP/3 measurement — Section 2.2 needs 3–5 stronger archival references

The current subsection has Varvello et al., one server-push paper, one HTTP/3 practitioner benchmark, Ruth et al., and domain sharding. 

paper(20260829-072146)

 Given that the report later presents 2,515 browser loads and discusses a substantial HTTP/2-versus-HTTP/3 concurrency effect, this literature needs to be deeper. 

paper(20260829-072146)

Add at minimum:

de Saxcé, Oprescu & Chen, “Is HTTP/2 Really Faster Than HTTP/1.1?”, IEEE ICC 2015.

Kakhki et al., “Taking a Long Look at QUIC: An Approach for Rigorous Evaluation of Rapidly Evolving Transport Protocols,” ACM IMC 2017.

Rüth et al., “A First Look at QUIC in the Wild,” PAM 2018.

More empirical HTTP/3/QUIC work on stream concurrency, loss, and implementation sensitivity.

This matters because your own result explicitly says the large HTTP/3 disadvantage is caused by the particular Caddy/quic-go/Chromium concurrency configuration rather than HTTP/3 intrinsically. 

paper(20260829-072146)

 The related work should make implementation sensitivity a known part of the literature rather than something appearing only after your experiment.

C. Small-image coding and multi-image containers — probably the largest conceptual omission

Section 2.3 currently concentrates on minimum file sizes, Cloudinary's AVIF cutoff, codec specifications, one AVIF study, and SSIM. 

paper(20260829-072146)

But Section 6.1 later introduces JPEG abbreviated format and animated WebP as intermediate points on the coupling spectrum. That is interesting and should have been established in Related Work. 

paper(20260829-072146)

I would explicitly cover:

JPEG abbreviated image data format / shared JPEG tables from T.81.

Animated WebP, where frames remain separately coded inside a common container.

APNG/MNG as historical multi-image PNG-family approaches.

HEIF/AVIF image collections/sequences as a modern multi-image packaging line.

The JPEG XL literature, especially Alakuijala et al., “JPEG XL next-generation image compression architecture and coding tools,” SPIE 2019, because JXL is already mentioned in your overhead discussion but has no substantive research treatment.

A short paragraph on thumbnail/small-object coding specifically: small images are unusual because framing/header cost is non-negligible relative to entropy-coded payload. That should be established as a research/engineering phenomenon rather than inferred primarily from one-pixel blog experiments.

This would also considerably strengthen the originality argument. Your novelty is then:

not “putting many images into one file,” but experimentally mapping where different degrees of coding-state coupling help or hurt under modern web codecs.

That is a stronger and more defensible claim.

D. Texture atlasing / sprite-sheet work — adequate start, but incorrectly narrow

Section 2.4 currently has Lévy et al., Jylänki, Unity documentation, and a 2002 Game Developer reference. 

paper(20260829-072146)

That is enough to establish texture atlases, but I would broaden it slightly to cover:

sprite-sheet generation and TexturePacker/Unity/major game-engine atlas tooling;

graphics work on padding/bleed, mipmapping, filtering boundaries, and texture-atlas layout;

virtual-texturing/texture-packing work where grouping and locality matter.

The key distinction should be explicit:

graphics atlasing optimizes GPU binding, locality, packing area, and filtering correctness; your work optimizes encoded byte size, adaptive codec state, network requests, and cache granularity.

That one paragraph would sharpen why the existing graphics literature does not subsume the paper.

E. Cache granularity and delta delivery deserves its own subsection

This is the most obvious missing literature thread because Section 6.2 makes delta delivery a substantial part of the practical recommendation. You model expected invalidation bytes and show dictionary deltas almost recovering individual-resource cache granularity. 

paper(20260829-072146)

Yet Related Work jumps directly from Brotli/zstd to Compression Dictionary Transport. 

paper(20260829-072146)

Add a new 2.5 Cache granularity, delta encoding, and shared dictionaries, including:

Mogul et al., RFC 3229, “Delta Encoding in HTTP” (2002).

VCDIFF, RFC 3284, and the associated differencing work by Korn/Vo.

Google's historical SDCH — Shared Dictionary Compression over HTTP.

Current HTTP caching semantics, RFC 9111.

Then Compression Dictionary Transport as the modern descendant.

This would prevent the current Section 6.2 from sounding as though dictionary-based incremental Web delivery first appeared with the recent CDT proposal.

Overall related-work judgment

Current: sufficient for a technical report and probably survivable at SPE.

For a polished archival submission: expand it. I would target 40–50 references, but more importantly build five recognizable literature threads rather than simply adding citations.

2. VISUALS
Figure 1 — 100-tile atlas

Useful, but the weakest analytical figure. It establishes concretely what an atlas looks like and gives the “147,361 B → 112,059 B” example, which is good for accessibility. 

paper(20260829-072146)

However, the image itself does little to explain the serving mechanism. For an SPE audience I would either:

retain it but turn it into a schematic showing 100 URLs → atlas.webp + coordinate map → CSS windows, or

combine the actual atlas image with this schematic.

That would earn its page space much better.

Figure 2 — photo-saving crossover

Strongest quantitative figure in the paper.

It immediately communicates the principal result: size dominates, JPEG remains positive, and WebP crosses zero around ~100 px. This is much easier to understand than finding the same pattern inside Table 1. 

paper(20260829-072146)

One important improvement: show the resampling uncertainty already reported in the text. You have 20 subset resamples and meaningful 95% intervals, including WebP's interval crossing zero near 112 px. 

paper(20260829-072146)

Add error bars or shaded CIs. That would transform Figure 2 from descriptive to genuinely publication-grade.

I would also annotate the approximate WebP break-even region rather than leaving readers to interpolate it themselves.

Figure 3 — network-speedup bars

Conceptually useful: it makes the main protocol result obvious. HTTP/2 reduces the benefit dramatically while HTTP/1.1 and this HTTP/3 deployment retain large benefits. 

paper(20260829-072146)

But it has two weaknesses.

First, the two panels use materially different vertical ranges. That makes visual comparison between flat art and photographs harder and potentially misleading. Use a common scale, or perhaps a log-speedup axis centered on 1×.

Second, because Table 4 already provides bootstrap intervals, bars are not the ideal mark. A dot-and-whisker plot showing median speedup + 95% CI would communicate both effect size and uncertainty and would handle values around 0.9–1.1× much better.

I would change Figure 3 from bars to point estimates with confidence intervals.

Figure 4 — warm-cache log plot

Also very strong. This is exactly the sort of plot the discussion needs: monolithic atlas is catastrophically expensive under low churn, chunking interpolates between extremes, and dictionary delta nearly tracks individual files. 

paper(20260829-072146)

The log scale is appropriate and the four curves correspond directly to deployment choices.

Keep it.

One correction: Section 6.2 says the warm-cache simulation is made explicit in “Table 4”, but Table 4 is the network-timing table; this should point to Figure 4. 

paper(20260829-072146)

Tables
Table 1 — main codec × size × N result

Scientifically central but visually dense. 

paper(20260829-072146)

I would keep the table because exact numbers matter, especially negative values. Figure 2 already gives the reader the major trend.

A heatmap could replace it, but I do not think that is necessary. The existing combination of Figure 2 + Table 1 is good.

Table 2 — SSIM tails

Useful and compact. It supports an important qualification: equal mean SSIM can conceal a bad worst-case WebP tile. 

paper(20260829-072146)

Keep it as a table. Four rows do not justify a separate plot.

If you wanted to strengthen this point experimentally, an ECDF of per-tile ΔSSIM for the problematic WebP case would be better than a prettier version of Table 2, but that would be a new analysis rather than mere presentation.

Table 3 — lossless/icon constructions

Good table. It makes the very large differences between WebP-lossless strip, shared-palette PNG, RGBA PNG, and JPEG concrete. 

paper(20260829-072146)

Could be a grouped bar chart, but I would not spend a figure on it. Keep.

Table 4 — network timing

Too large for the main narrative.

It is 24 experimental cells with absolute timings, four serving methods, and two speedup columns. The data are valuable, but Figure 3 already communicates the conclusion. 

paper(20260829-072146)

For SPE I would:

retain a reduced summary table in the paper,

move the complete table to appendix/supplement,

let revised Figure 3 carry the primary message.

This would materially improve readability.

Table 5 — heuristic versus oracle

Important because this is what converts the paper from a measurement study into a deployable software/practice contribution. 

paper(20260829-072146)

Keep it.

However, five rows of exactly 0.0% regret look almost suspiciously perfect. The explanation is legitimate—some candidate representations are byte-equivalent—but the table would be more convincing if it also included one or two naive baselines:

always WebP atlas, always byte-bundle, perhaps individual files.

Then Table 5 would demonstrate not merely “our heuristic equals our candidate-set oracle” but “the calibrated policy materially outperforms simple deployable rules.”

That would substantially strengthen Section 6.3.

The one NEW figure I would add
A decision-flow / construction-heuristic diagram

This would provide the most value at SPE.

Section 6.3 currently describes an actual deployable procedure entirely in prose: deduplicate; partition by cadence/lossless/dimensions; choose pixel atlas, byte-bundle, or individual files; chunk; emit CSS/loader. 

paper(20260829-072146)

Convert that to approximately:

Input directory
→ exact duplicate elimination
→ group by dimensions/update cadence
→ lossless required?
→ small homogeneous tiles?
→ candidate encoding/layout
→ WebP-lossless strip / shared-palette PNG / tuned lossy WebP / byte-bundle
→ choose measured smaller candidate
→ chunk for memory/cache budget
→ optional dictionary-delta updates
→ atlas + manifest + CSS/loader.

That is precisely the “practice and experience” part of the paper.

My second-choice new figure would be a coupling-spectrum diagram for Section 6.1:

individual → byte-bundle → shared tables / multi-image container → pixel atlas

with increasing sharing of:

transport → headers → tables → entropy/adaptive state

and arrows showing fixed-cost saving ↑ but adaptive coupling risk ↑.

The coupling idea is currently one of the intellectually strongest parts of the report but exists only as prose and equations. 

paper(20260829-072146)

If page budget allows, I would actually include both; if only one, choose the heuristic flowchart for SPE.

3. TOP CHANGES TO MOVE FROM “CLEAN ACCEPT” TOWARD “STRONG ACCEPT”

Ranked by impact / effort:

1. Expand Related Work and reposition the novelty around the coupling design space

Impact: very high | Effort: low–moderate

This is the most obvious remaining journal-level weakness.

Add the five threads above, especially multi-image containers/shared JPEG tables and historical delta encoding. Then make the novelty claim narrower and stronger:

this is not the first image atlas; it is a systematic matched-quality characterization of coding-state coupling versus fixed-cost amortization for small web images, connected to a deployable policy.

That aligns much better with what Section 6.1 actually demonstrates. 

paper(20260829-072146)

2. Make Section 6.3 visibly the paper's software contribution

Impact: very high | Effort: low

Add the heuristic flowchart and augment Table 5 with simple baselines.

At present, the tool is genuinely useful—it produces bundles, coordinate maps, loader code, and savings reports, and matches the restricted oracle on five unseen corpora—but readers have to reconstruct the algorithm from prose. 

paper(20260829-072146)

For Software: Practice and Experience, this is probably the single easiest way to raise perceived contribution.

3. Add one modern perceptual-quality cross-check

Impact: high | Effort: moderate

The paper itself identifies luma SSIM as a limitation and specifically names SSIMULACRA2/butteraugli. 

paper(20260829-072146)

You do not need to reproduce every experiment. Re-run the important lossy crossovers:

56/112/224 px photographs,

JPEG and WebP,

individual versus atlas,

perhaps the tuned-WebP 224 px result,

using SSIMULACRA2.

If the WebP zero crossing and the +5% tuned-WebP result survive, one major reviewer objection disappears.

4. De-risk the HTTP/3 result

Impact: high | Effort: moderate–high

The paper correctly acknowledges that HTTP/3's 4–5× individual-file slowdown relative to HTTP/2 is caused by the particular stream/concurrency behavior of this stack and is not intrinsic HTTP/3 behavior. 

paper(20260829-072146)

For a strong accept, either:

confirm the diagnosis using qlog plus one second server/QUIC implementation or native Linux, or

further weaken the conclusion so that HTTP/3 is clearly a case study in deployment configuration rather than a general protocol result.

The current limitations section already identifies exactly this experiment. 

paper(20260829-072146)

Because Figure 3 makes the HTTP/3 effect visually prominent, a reviewer can otherwise spend disproportionate effort attacking what is supposed to be supporting evidence.

5. Tighten the presentation around the central empirical laws

Impact: moderate | Effort: low

Specifically:

add CIs to Figure 2;

turn Figure 3 into CI dot/whisker plots;

move most of Table 4 to supplementary material;

add the heuristic flowchart;

fix cross-reference errors, including the Section 6.2 “Table 4” → Figure 4 issue;

consider a small coupling-spectrum schematic if space permits.

The report already has plenty of measurements. What it now needs is less visual density and a clearer hierarchy of findings, not additional minor experiments.

Bottom line

The experimental and practice sides are now stronger than the literature framing. The most valuable next step is not another broad experiment: expand Section 2, visually formalize the construction heuristic, add a small SSIMULACRA2 robustness check, and either validate or tightly contain the HTTP/3 implementation-specific finding. With those changes, the manuscript would look much more like a mature archival SPE article rather than an unusually thorough technical report.