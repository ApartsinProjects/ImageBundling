1. SCOPE FIT FOR IEEE TMM

Fit: defensible, but borderline. This is not obviously out of scope for IEEE Transactions on Multimedia: the paper jointly studies image coding behavior, multi-image representation, browser decoding/rendering, cache behavior, and network delivery. Its central technical object is a collection of visual media assets and the trade-off between independently coded images and jointly represented image bundles. The claimed contributions span matched-quality image compression, HTTP delivery, codec-aware packing, and a deployment optimizer. 

paper(20260829-023030)

However, the paper currently reads more like a strong web-performance/measurement paper than a TMM paper. The main question is essentially “does the old CSS-sprite idea still help under modern codecs and HTTP/2/3?” TMM reviewers normally expect the multimedia representation/coding/system contribution to be primary, with the web serving environment as the application. Here, HTTP behavior and browser engineering occupy enough of the argument that an editor could reasonably decide that the natural audience is web systems/network measurement rather than multimedia.

Would I expect a desk rejection?

Not automatically. I would estimate roughly a 25–35% desk-reject-on-fit risk as written. The title helps because it explicitly says “codecs,” but “Web Images,” CSS atlasing, HTTP/1.1/2/3, Caddy, Chromium, and page-load timing can push the manuscript toward the web-systems side.

The strongest TMM positioning is:

Primary: multimedia systems / multimedia communications and delivery.
Secondary: image coding/compression and rate-quality optimization.

I would not position it as primarily an image-codec paper, because there is no new codec or coding tool. I would position it as a codec-aware joint representation and delivery system for collections of visual media objects.

That distinction matters.

2. TMM REFEREE SUMMARY AND RECOMMENDATION
Summary

The manuscript revisits image atlasing as a joint representation mechanism for collections of small web images. It argues that bundling can recover both per-file structural overhead and cross-image redundancy, but can also lose efficiency when a codec's adaptive state is forced to be shared across heterogeneous tiles. It experimentally studies JPEG, PNG, lossy/lossless WebP over multiple tile sizes and collection sizes, adds packing/order/chunking techniques, measures HTTP/1.1, HTTP/2 and HTTP/3 page-load behavior, analyzes cache invalidation, and packages the observations into a construction heuristic. 

paper(20260829-023030)

The strongest intellectual element is the fixed-cost versus adaptive-state “coupling spectrum.” The manuscript does more than show that sprites sometimes save bytes: it attempts to explain why JPEG behaves differently from WebP and PNG, why vertical strips help PNG, and why a zero-coupling byte bundle is appropriate for heterogeneous content. 

paper(20260829-023030)

 The encoder-tuning result is also interesting: changing WebP settings reportedly turns a −9% photographic-atlas penalty into a +5% gain at matched SSIM. 

paper(20260829-023030)

The empirical work is substantial. There is randomized subset resampling for the principal byte crossover result, with bootstrap intervals showing the 56/112/224-pixel regimes are not merely artifacts of a single subset. 

paper(20260829-023030)

 The paper also goes beyond a single atlas baseline through clustering, strip packing, explicit duplicate handling, byte bundles, chunking, and dictionary-delta updates. 

paper(20260829-023030)

Recommendation: Reject in present form, with encouragement to resubmit after substantial expansion

For a generic web/systems venue I would be considerably more positive. For TMM specifically, the manuscript is one substantial experimental round short of the Transactions bar.

My main reasons are:

The multimedia novelty is currently empirical rather than methodological. Atlasing is old; the new contribution is chiefly a careful characterization of when it works. The “coupling spectrum” is promising, but currently functions as a post-hoc explanatory framework rather than a predictive model or algorithm.

The codec comparison is incomplete for TMM. The paper deliberately limits itself to JPEG/PNG/WebP, even though it explicitly acknowledges that AVIF is already material and that AVIF/JPEG XL would alter the crossover. 

paper(20260829-023030)

 That is a reasonable product-engineering scope restriction, but a weak restriction for an archival multimedia journal.

The rate-distortion methodology is below what codec-oriented TMM reviewers will expect. The entire lossy comparison rests primarily on mean per-tile luma SSIM at a single 0.97 operating point, using a five-value encoder-quality ladder and occasionally abandoning interpolation when it becomes unstable. 

paper(20260829-023030)

The systems evidence is extensive but not sufficiently externally validated. One Chromium/Caddy/WSL2 setup under emulated networks is useful engineering evidence, but the very unusual HTTP/3 behavior becomes part of the headline results.

There is an important baseline-optimality question: individually coded images appear to use common encoder-quality settings rather than per-image rate allocation. A TMM coding reviewer will ask whether separate images were allowed to exploit their natural advantage by independently selecting the minimum rate necessary to satisfy each image's quality constraint.

My score would therefore be approximately borderline reject / weak reject on technical merit, clearer reject once TMM-specific expectations are applied.

3. WHAT TMM REVIEWERS ARE LIKELY TO DEMAND
A. AVIF is effectively mandatory; JPEG XL is highly desirable

The paper's “universally supported web codecs” justification is practical, but TMM is not a browser-compatibility journal. The related-work section already recognizes AVIF/JPEG XL and modern rate-distortion literature, but neither is evaluated. 

paper(20260829-023030)

 The limitations section itself concedes this and says AVIF is the first codec a follow-up should add. 

paper(20260829-023030)

For TMM:

AVIF should be added.

JPEG XL should preferably be added as a scientific comparator, even if browser deployment constraints prevent it from being part of every networking experiment.

Ideally evaluate a standardized multi-image/container alternative where applicable, rather than comparing only independent files, pixel atlases and the custom byte bundle.

This is particularly important because the paper's proposed principle is supposed to be codec-general. A genuinely new codec with different prediction/adaptation/container behavior is exactly the test needed to establish generality.

B. One SSIM point is not sufficient rate-distortion evidence

The manuscript uses mean per-tile luma SSIM = 0.97, interpolated over only five encoder settings. 

paper(20260829-023030)

 It later admits that interpolation becomes unstable for nearly coincident curves. 

paper(20260829-023030)

A TMM reviewer is likely to request:

full rate-distortion curves;

considerably denser encoder sweeps;

BD-rate/BD-quality comparisons over a meaningful quality range rather than only one threshold;

PSNR/YUV or RGB metrics for reproducibility;

MS-SSIM;

a stronger perceptual metric such as SSIMULACRA2 or Butteraugli;

potentially LPIPS/DISTS or a similarly established perceptual IQA metric.

VMAF can be included, but I would not make it the primary additional metric for still images. SSIMULACRA2/Butteraugli plus MS-SSIM would be more directly informative here.

There is also a terminology problem: a mean SSIM of 0.97 is not a “per-tile quality floor.” A few poor tiles can be compensated by many very good ones. If the paper promises a floor, report something such as minimum, 5th percentile, or a constraint such as ≥95% of tiles exceeding the target.

This is particularly important for atlasing because the damage may be concentrated around specific tile boundaries.

C. The independent-image baseline needs stronger rate allocation

This is the most important technical issue that is not already acknowledged in the limitations.

For independent files, each image can have its own optimal quality/quantization configuration. If the objective is

min
i
∑
	​

R
i
	​

s.t. quality constraints,

the correct individual-image baseline should choose a separate operating point q
i
	​

 for every image. Applying the same nominal encoder-quality setting across the entire corpus does not generally minimize total rate.

The atlas is intrinsically constrained to shared coding decisions; independent files are not.

Therefore I would require one of two protocols:

Per-tile constraint: independently choose the lowest-rate encoding of every tile that achieves SSIM/MS-SSIM/etc. ≥ target.

Aggregate distortion constraint: optimize bit allocation across the independent files to minimize total bytes subject to the same aggregate distortion as the atlas.

If the 20–30% JPEG and 10–20% WebP results survive this stronger baseline, the paper becomes much more convincing.

D. Subjective validation is highly advisable

The paper itself admits that luma SSIM is a limitation. 

paper(20260829-023030)

I do not think TMM necessarily requires a massive MOS experiment here, but given that the central comparison depends on calling two conditions “matched quality,” a small controlled subjective study would materially improve credibility.

It should concentrate on precisely the artifacts where atlasing can behave differently:

blocking/bleeding across tile boundaries;

flat-art edges;

chroma changes ignored by luma SSIM;

heterogeneous photographic atlases;

default versus tuned WebP.

A pairwise study or DSIS-style experiment on representative tiles would be sufficient; hundreds of subjects are unnecessary.

E. Network statistical rigor needs repair

There is an immediate internal inconsistency.

Section 4.3 says that after discarding the warm-up there are 11 measured loads per cell. 

paper(20260829-023030)

 Table 2 instead says n = 7 cold loads per cell. 

paper(20260829-023030)

That has to be reconciled before submission.

More generally, the limitations already concede that the network results use small per-cell samples and do not report full dispersion/significance testing. 

paper(20260829-023030)

 For TMM I would expect:

CIs for every principal latency comparison;

effect sizes rather than only medians;

a consistent definition of n;

substantially more repetitions for noisy/lossy conditions;

preferably repeated runs on at least another host/platform;

explicit random seeds and loss models.

The byte experiments are actually statistically cleaner than the network section because the random-subset bootstrap study directly addresses corpus-composition sensitivity. 

paper(20260829-023030)

F. The HTTP/3 result needs considerably stronger causal evidence

This is likely to attract a systems-oriented TMM referee immediately.

The paper finds that individual-file HTTP/3 is 4–5× slower than HTTP/2 even without packet loss, attributes this to observed concurrency of approximately 6 versus 13–14 requests, and then ascribes that to QUIC stream limits/flow control and Chromium/Caddy behavior. 

paper(20260829-023030)

But the limitations simultaneously acknowledge that this explanation is inferred from Resource Timing and has not been validated with qlog traces or across servers/native Linux. 

paper(20260829-023030)

Therefore the current language is too causal.

For TMM, either:

validate it with qlog/transport traces and explicit stream-limit experiments across at least two HTTP/3 stacks; or

demote it to a testbed-specific observation and remove it from any general conclusion about HTTP/3.

There is a related wording problem in the abstract: it says chunking under packet loss helps by “spreading the transfer across connections.” 

paper(20260829-023030)

 That is straightforward for the HTTP/1.1 case discussed later, but HTTP/2/3 same-origin chunks normally mean additional streams within a connection rather than automatically additional connections. The mechanism needs protocol-specific wording.

G. TMM will expect multimedia-system QoE/resource metrics, not only page completion

The current system metric is principally time to all tiles visible. 

paper(20260829-023030)

 The paper analytically discusses decoded memory, but does not measure it in the browser. 

paper(20260829-023030)

For a multimedia systems paper, I would add:

image decode CPU time;

peak decoded memory;

first-visible/above-the-fold completion;

LCP or a comparable user-perceived loading metric;

scrolling/paint behavior for a large atlas;

warm-cache navigation.

This matters because the main engineering drawback of a large atlas is exactly that it changes the decode and residency unit from individual media objects to an entire image.

H. The heuristic currently has circular validation

The paper says the optimizer is calibrated from the measured curves and is then “validated against the study's own asset sets.” 

paper(20260829-023030)

That will not establish algorithmic novelty at TMM.

The optimizer needs:

held-out image libraries;

an explicit cost function;

strong simple baselines;

an oracle/near-oracle for small instances;

ablations for deduplication, clustering, codec selection and chunk sizing;

generalization to codecs/content not used in calibration.

This is an important route to turning the manuscript into a true TMM systems contribution.

I. Related work is too web-heavy for TMM

The manuscript contains useful web/network references, standards and practitioner sources. But its multimedia-coding discussion is comparatively thin; among the concluding references, for example, the obvious modern codec comparison is essentially one AVIF paper plus a texture-atlas paper. 

paper(20260829-023030)

A TMM submission needs a substantially deeper archival discussion of:

multi-image/joint image coding;

image collections and image grids;

tile-based coding;

texture-atlas compression;

small-image coding;

perceptual rate-distortion optimization;

image/video delivery and multimedia QoE.

The novelty statement that no prior matched-quality image-atlasing study exists is currently plausible, but not sufficiently defended for a Transactions paper.

4. SINGLE BIGGEST ACCEPTANCE RISK
The paper can be judged as “excellent measurement of an old web technique, but insufficient new multimedia methodology.”

That is more dangerous than any individual missing codec or metric.

The current five contributions include extensive measurements, engineering techniques, a conceptual coupling explanation, and a heuristic. 

paper(20260829-023030)

 But a skeptical TMM reviewer can reduce them to:

CSS sprites are old; bundling amortizes headers; heterogeneous images sometimes compress worse together; HTTP requests have overhead.

The existing experiments make that much more nuanced, but a Transactions reviewer can still ask, “What is the new general multimedia method?”

Best way to de-risk it

Make the coupling model + representation optimizer the central scientific contribution rather than “sprites are still useful.”

A stronger paper would formulate:

representation selection=fixed-cost gain−adaptive-coupling penalty+transport/cache/decode costs,

derive measurable predictors from the source collection and codec, and then predict the best representation on held-out corpora/codecs.

AVIF is particularly useful here: it becomes not merely another baseline, but a prospective test of the coupling hypothesis.

If the framework predicts when AVIF/JPEG/WebP/PNG should use independent images, joint atlases, strips, chunks or zero-coupling bundles, the contribution becomes much more recognizably TMM.

5. PRIORITIZED REVISION PLAN
Priority	Revision	Effort	Expected impact
1	Replace the single-q independent baseline with per-image rate-distortion optimization; generate dense RD curves and BD-rate results.	Medium–High	Very high
2	Add AVIF throughout the core byte experiments; add JPEG XL at least as an offline coding comparator. Test the coupling hypothesis prospectively rather than merely adding two table columns.	Medium–High	Very high
3	Turn the coupling spectrum into a quantitative predictive model and evaluate the optimizer on held-out corpora/codecs. Compare against individual, monolithic atlas, fixed chunking and an oracle on tractable subsets.	High	Very high / addresses novelty directly
4	Replace luma-SSIM-only evaluation with MS-SSIM + SSIMULACRA2/Butteraugli + conventional PSNR/RGB/YUV reporting; enforce/report tile-level quality percentiles.	Medium	High
5	Add a focused subjective validation. Representative photographic, icon and boundary-artifact conditions rather than a huge MOS study.	Medium	High
6	Repair and strengthen the network experiment. Resolve 7-versus-11 runs; increase repetitions; give CIs/effect sizes; run native Linux and preferably a second server stack.	Medium–High	High
7	Either prove the HTTP/3 concurrency explanation with qlog/config manipulation or sharply narrow the claim. Do not present one Caddy/Chromium configuration as generic HTTP/3 behavior.	Medium	High
8	Measure decode time and peak renderer memory experimentally. Add first/above-fold completion and warm-cache behavior alongside all-tiles-visible.	Medium	Medium–High
9	Broaden the real image corpus substantially. Multiple photo datasets/icon libraries plus trace-like heterogeneous collections; report distributions rather than only one calibrated crossover. The paper itself already identifies this limitation. 

paper(20260829-023030)

	Medium	Medium–High
10	Rebuild Related Work around multimedia/image-coding literature rather than web-practitioner literature. Position HTTP as the delivery application of a general many-image representation problem.	Medium	High for TMM fit
11	Move some deployment engineering out of the main narrative. CSS syntax and some detailed cache implementation material can be shortened or moved to supplementary material, giving more room to RD methodology, codec analysis and predictive modeling.	Low	Medium
12	Retitle/reframe the paper around joint representation rather than “revisiting” CSS sprites. The current wording encourages reviewers to interpret the contribution as resurrecting an old web optimization.	Low	Medium
Acceptance probability

These are referee-style judgment estimates, not journal statistics.

As submitted: ~10–15% probability of eventual TMM acceptance. The underlying work is substantive, but there is a meaningful scope/novelty risk plus several experiments that a TMM codec/systems reviewer can reasonably regard as mandatory.

After only adding AVIF + extra IQA metrics: approximately 20–30%. That fixes obvious reviewer objections but does not solve the central novelty problem.

After the full high-priority revision above, assuming the main results survive the stronger independently optimized baseline: approximately 45–55%. The decisive improvement would come from transforming the paper from an empirical “image bundling revisited” study into a general codec-aware joint-representation and multimedia-delivery optimization framework, validated prospectively across modern codecs and held-out image collections.