"""Build docs/paper.html, the technical report, from results data. House style: SynSmith.

One command regenerates the paper; tables and charts are pulled from results JSON so the
paper cannot go stale relative to the data. Canaries: report fails loudly if expected
figures, tables, or sections are missing from the output.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from make_results_page import bar_chart, svg_chart  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent

CSS = """
body{font-family:"Charter","Iowan Old Style","Source Serif Pro",Georgia,"Times New Roman",serif;
 color:#111418;background:#fff;max-width:720px;margin:2.5rem auto;padding:0 1rem;
 font-size:11pt;line-height:1.55;text-align:justify;hyphens:auto}
code,pre{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;background:#f4f5f7;font-size:9.5pt}
pre{padding:.5rem .8rem;overflow-x:auto;text-align:left;line-height:1.4;margin:.7rem 0}
pre+p{text-indent:0}
h1{font-size:19pt;font-weight:600;text-align:center;line-height:1.25;margin:0 0 .4rem}
.authors{text-align:center;font-size:10.5pt;color:#2c3138;margin-bottom:.2rem}
.venue{text-align:center;font-size:9.5pt;color:#5a626c;margin-bottom:1.6rem}
h2{font-size:13pt;font-weight:700;color:#14385c;margin:1.6rem 0 .5rem;text-align:left}
h3{font-size:11.5pt;font-weight:700;margin:1.1rem 0 .35rem;text-align:left}
.abstract{margin:1.2rem 2.2rem}
.abstract .ahead{text-align:center;font-variant:small-caps;letter-spacing:.08em;font-size:11pt;margin-bottom:.3rem}
.abstract p{font-size:10pt;text-indent:0}
p{margin:0;text-indent:1.4em}
h2+p,h3+p,figure+p,.tablewrap+p,.abstract+p,div+p{text-indent:0}
figure{margin:1.1rem 0;text-align:center}
figure img,figure svg{max-width:100%;border:1px solid #d1d4d8}
figcaption{font-size:9.5pt;color:#5a626c;text-align:justify;margin-top:.35rem;text-indent:0}
.tablewrap{overflow-x:auto;margin:1.1rem 0}
table{border-collapse:collapse;margin:0 auto;font-size:9.5pt}
th,td{padding:2.5px 9px;text-align:right;border:none}
td:first-child,th:first-child{text-align:left}
thead th{border-bottom:1px solid #111418}
table{border-top:1.5px solid #111418;border-bottom:1.5px solid #111418}
caption{font-size:9.5pt;color:#5a626c;margin-bottom:.3rem;caption-side:top;text-align:justify}
.refs{font-size:9pt}
.refs p{text-indent:-1.4em;padding-left:1.4em;margin-bottom:.25rem}
a{color:#14385c}
.footer{font-size:9pt;color:#5a626c;text-align:center;margin:2.5rem 0 1rem;border-top:1px solid #d1d4d8;padding-top:.6rem}
.neg{color:#8a2f22}
"""


def load(tag):
    return json.load((ROOT / "results" / "static" / tag /
                      "matched_quality_savings.json").open())


def load_network(tag="phase2_full"):
    f = ROOT / "results" / "network" / tag / "summary.json"
    return json.load(f.open()) if f.exists() else None


def network_results_html():
    """Table 2 + Figure 4 from the network summary; empty string if not yet run."""
    summ = load_network()
    if not summ:
        return ""
    med = {(s["profile"], s["proto"], s["cls"], s["n"], s["cond"]): s["median_ms"]
           for s in summ}
    profiles = [("localhost", "localhost"), ("fast", "100 Mbit / 20 ms"),
                ("cell4g", "9 Mbit / 60 ms"), ("slow3g", "1.6 Mbit / 150 ms"),
                ("lossy4g", "9 Mbit / 60 ms / 1% loss")]
    trows = []
    for cls in ["emoji", "photos"]:
        for pkey, plabel in profiles:
            cells = []
            for proto in ["h1", "h2", "h3"]:
                i = med.get((pkey, proto, cls, 500, "individual"))
                a = med.get((pkey, proto, cls, 500, "atlas1"))
                cells.append(f"<td>{i:,.0f}</td><td>{a:,.0f}</td>"
                             f"<td><b>{i/a:.1f}x</b></td>" if i and a
                             else "<td>&mdash;</td>" * 3)
            trows.append(f"<tr><td>{cls}</td><td>{plabel}</td>{''.join(cells)}</tr>")
    table2 = ("<div class='tablewrap'><table>"
              "<caption><b>Table 2.</b> Median time to all 500 tiles visible (ms), "
              "individual files vs one atlas, and the atlas speedup, per protocol and "
              "network profile (8 cold loads per cell, first load dropped; WebP-class "
              "payload sizes).</caption>"
              "<thead><tr><th>class</th><th>network</th>"
              "<th>h1 ind</th><th>h1 atl</th><th>x</th>"
              "<th>h2 ind</th><th>h2 atl</th><th>x</th>"
              "<th>h3 ind</th><th>h3 atl</th><th>x</th></tr></thead>"
              f"<tbody>{''.join(trows)}</tbody></table></div>")

    # Figure 4: speedup bars, groups = profile, bars = protocol, panel per class
    def panel(cls, label):
        W, H, ML, MB, MT, MR = 520, 260, 56, 46, 16, 96
        vals = {}
        for pi, (pkey, _) in enumerate(profiles):
            for proto in ["h1", "h2", "h3"]:
                i = med.get((pkey, proto, cls, 500, "individual"))
                a = med.get((pkey, proto, cls, 500, "atlas1"))
                if i and a:
                    vals[(pkey, proto)] = i / a
        ymax = max(vals.values()) + 1
        gw = (W - ML - MR) / len(profiles)
        bw = min(16.0, (gw - 12) / 3)
        pc = {"h1": "#c0392b", "h2": "#2980b9", "h3": "#8e44ad"}
        out = [f'<svg viewBox="0 0 {W} {H}" style="max-width:100%" '
               f'font-family="Georgia,serif" role="img" aria-label="Atlas speedup, {cls}">']

        def Y(s):
            return (H - MB) - (H - MB - MT) * s / ymax
        for g in range(0, int(ymax) + 1, 2):
            out.append(f'<line x1="{ML}" y1="{Y(g):.0f}" x2="{W-MR}" y2="{Y(g):.0f}" '
                       f'stroke="#eee"/><text x="{ML-6}" y="{Y(g)+4:.0f}" font-size="10" '
                       f'text-anchor="end" fill="#5a626c">{g}x</text>')
        out.append(f'<line x1="{ML}" y1="{Y(0):.0f}" x2="{W-MR}" y2="{Y(0):.0f}" stroke="#999"/>')
        for pi, (pkey, _) in enumerate(profiles):
            x0 = ML + pi * gw + (gw - bw * 3) / 2
            for bi, proto in enumerate(["h1", "h2", "h3"]):
                s = vals.get((pkey, proto))
                if not s:
                    continue
                out.append(f'<rect x="{x0+bi*bw:.1f}" y="{Y(s):.1f}" width="{bw-2:.1f}" '
                           f'height="{Y(0)-Y(s):.1f}" fill="{pc[proto]}"/>')
            short = {"localhost": "local", "fast": "fast", "cell4g": "4G",
                     "slow3g": "3G", "lossy4g": "4G+loss"}[pkey]
            out.append(f'<text x="{ML+pi*gw+gw/2:.0f}" y="{H-MB+16}" font-size="10" '
                       f'text-anchor="middle" fill="#5a626c">{short}</text>')
        out.append(f'<line x1="{ML}" y1="{Y(1):.1f}" x2="{W-MR}" y2="{Y(1):.1f}" '
                   f'stroke="#111418" stroke-dasharray="4 3"/>')
        out.append(f'<text x="{(ML+W-MR)/2:.0f}" y="{H-8}" font-size="11" '
                   f'text-anchor="middle" fill="#111418">network profile</text>')
        out.append(f'<text x="14" y="{(MT+H-MB)/2:.0f}" font-size="11" text-anchor="middle" '
                   f'fill="#111418" transform="rotate(-90 14 {(MT+H-MB)/2:.0f})">'
                   f'atlas speedup (individual / atlas)</text>')
        out.append(f'<text x="{ML+6}" y="{MT+12}" font-size="12" font-weight="bold" '
                   f'fill="#111418">{label}</text>')
        lx, ly, lh = W - MR + 12, MT + 6, 17
        out.append(f'<rect x="{lx-6}" y="{ly-12}" width="{MR-14}" height="{3*lh+16}" '
                   f'fill="#fff" stroke="#d1d4d8"/>')
        for i, proto in enumerate(["h1", "h2", "h3"]):
            yy = ly + i * lh
            lab = {"h1": "HTTP/1.1", "h2": "HTTP/2", "h3": "HTTP/3"}[proto]
            out.append(f'<rect x="{lx}" y="{yy-7}" width="12" height="10" fill="{pc[proto]}"/>'
                       f'<text x="{lx+16}" y="{yy+2}" font-size="9" fill="#111418">{lab}</text>')
        out.append('</svg>')
        return "".join(out)

    fig4 = (f"<figure>{panel('emoji', '(a) flat art, 72px, N=500')}"
            f"{panel('photos', '(b) photos, 224px, N=500')}"
            "<figcaption><b>Figure 4.</b> Time-to-all-tiles-visible speedup from "
            "bundling (median individual / median single atlas) at N&nbsp;=&nbsp;500, "
            "per protocol and network profile. The dashed line marks parity. "
            "Multiplexing (HTTP/2/3) narrows the gap relative to HTTP/1.1 but never "
            "closes it.</figcaption></figure>")
    return table2 + fig4


def main():
    rows = load("phase1_emoji") + load("phase1_photos")
    ex = json.load((ROOT / "docs" / "img" / "examples.json").open())

    def cell(cls, n, codec):
        for r in rows:
            if (r["class"], r["n"], r["codec"], r["pad"]) == (cls, n, codec, 0) and \
               r["ssim_target"] in (0.97, None):
                s = r["saving_pct"]
                mark = "&ge;" if r.get("lower_bound") else ""
                klass = ' class="neg"' if s < 0 else ""
                return f"<td{klass}>{mark}{s:.1f}</td>"
        return "<td>&mdash;</td>"

    codecs = ["jpeg", "webp", "png", "webp_ll"]
    heads = ["JPEG", "WebP", "PNG", "WebP-lossless"]
    trows = []
    for cls, label in [("emoji", "flat art 72px"), ("photos", "photos 224px")]:
        for n in [10, 50, 200, 500]:
            trows.append(f"<tr><td>{label}</td><td>{n}</td>" +
                         "".join(cell(cls, n, c) for c in codecs) + "</tr>")
    table1 = ("<div class='tablewrap'><table>"
              "<caption><b>Table 1.</b> Bytes saved by atlasing (%) at matched per-tile "
              "SSIM 0.97 (lossy codecs; interpolated on the quality ladder) or exact "
              "lossless comparison (-ll columns), grid packing, no padding. Negative "
              "values (red) mean the atlas is larger.</caption>"
              f"<thead><tr><th>class</th><th>N</th>{''.join(f'<th>{h}</th>' for h in heads)}"
              f"</tr></thead><tbody>{''.join(trows)}</tbody></table></div>")

    emoji_ex = next(e for e in ex if e["class"] == "emoji")
    s = emoji_ex["stats"]["JPEG q80"]
    fig_atlas = (f"<figure><img src='img/{emoji_ex['file']}' alt='100-emoji atlas'>"
                 f"<figcaption><b>Figure 1.</b> A {emoji_ex['n']}-tile atlas "
                 f"({emoji_ex['grid']} grid of {emoji_ex['tile']}px tiles, "
                 f"{emoji_ex['atlas_px']}px). Encoded with identical settings both ways, the "
                 f"{emoji_ex['n']} tiles cost {s['individual']:,} bytes as separate JPEG files and "
                 f"{s['atlas']:,} bytes as this single JPEG ({s['saving_pct']:.0f}% less), "
                 f"while {emoji_ex['n']} HTTP requests become one. Each tile is displayed "
                 f"with CSS <code>background-position</code>.</figcaption></figure>")

    bars_e = bar_chart(load("phase1_emoji"), "emoji", 0.97, 0, "(a) flat art, 72px")
    bars_p = bar_chart(load("phase1_photos"), "photos", 0.97, 0, "(b) photos, 224px")
    fig_bars = (f"<figure>{bars_e}{bars_p}"
                "<figcaption><b>Figure 2.</b> Bytes saved by atlasing per codec at matched "
                "per-tile SSIM 0.97 (lossless codecs compared exactly), for (a) 72px "
                "flat-art tiles and (b) 224px photographic thumbnails. Bar shade encodes "
                "the number of bundled images N. Bars below zero mean the atlas is larger "
                "than the same tiles as individual files.</figcaption></figure>")
    chart_e = bar_chart(load("phase1_emoji"), "emoji", 0.97, 0,
                        "(a) flat art, 72px", group_by="n")
    chart_p = bar_chart(load("phase1_photos"), "photos", 0.97, 0,
                        "(b) photos, 224px", group_by="n")
    fig_charts = (f"<figure>{chart_e}{chart_p}"
                  "<figcaption><b>Figure 3.</b> The same savings as Figure 2 grouped "
                  "by image count N, one codec-colored bar per group: (a) 72px flat "
                  "art, (b) 224px photographic thumbnails. Savings grow with N and "
                  "saturate near N&nbsp;=&nbsp;200, once hundreds of per-file container "
                  "overheads have collapsed into one; the per-codec ordering follows the "
                  "per-codec container floors.</figcaption></figure>")

    html = f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Image Bundling Revisited</title><style>{CSS}</style></head><body>
<h1>Image Bundling Revisited: Optimal Atlasing of Small Web Images under Modern Codecs
and Protocols</h1>
<div class="authors">Alexander Apartsin</div>
<div class="venue">MPCode Technical Report &middot; original project MPCode 2001 &middot; revisited 2026</div>

<div class="abstract"><div class="ahead">Abstract</div>
<p>Web pages routinely load tens to hundreds of small images; the median mobile page
carries 13 image elements and the 90th percentile carries 56. Serving each image as a
separate resource pays three costs: per-request protocol overhead, a fixed per-file
structural cost (headers, coding tables, container chunks; roughly 600 bytes for a
JPEG), and the loss of cross-image redundancy that a codec can exploit only within one
file. This report measures how much of these costs bundling recovers when many small
images are packed into a single atlas image and displayed with standard CSS. The study
focuses on the three formats that carry the overwhelming majority of web images today
and decode in every browser: JPEG, PNG, and WebP. At matched per-tile quality (SSIM
0.97), atlasing 500 72-pixel flat-art tiles saves 26&ndash;34% of bytes under JPEG and
8&ndash;17% under WebP, and the saving is protocol-independent. The saving is governed
by the ratio of per-file structural cost to content bytes: for 224-pixel photographic
thumbnails it shrinks to a few percent under JPEG and inverts into a cost under WebP
and the lossless formats, whose per-image adaptation outperforms any single global
model. These measurements yield a codec-aware bundling rule: atlas small lossy tiles,
never lossless assets or large photographic tiles. Beyond the
binary decision, the report formulates atlas construction as an optimization problem:
partition a page's image set into bundles, and order tiles within each bundle, to
minimize a cost combining bytes per deploy under cache invalidation, load latency for
the target protocol and network, and decoded memory, subject to a per-tile quality
floor. A companion network study measures the end-to-end timing effect across HTTP/1.1,
HTTP/2, and HTTP/3 under emulated network conditions on the same testbed.</p></div>

<h2>1&nbsp;&nbsp;Introduction</h2>
<p>Product grids, icon sets, avatars, and decorative elements make small images the most
numerous resource class on commercial pages. Bundling them into one image, the CSS
sprite technique, was standard practice in the HTTP/1.1 era and fell out of favor when
HTTP/2 multiplexing removed the per-connection request bottleneck. That reasoning
addressed only the request-count cost. Two byte-level costs survive multiplexing
untouched: every image file carries a fixed container overhead (headers, quantization
tables, ISOBMFF boxes), and every file boundary prevents the codec from sharing entropy
context, palettes, and predictors across images.</p>
<p>The study is deliberately scoped to the popular, universally-supported compressed
formats: JPEG, PNG, and WebP together carry over 70% of images served on the web (HTTP
Archive 2024: JPEG 32.4%, PNG 28.4%, WebP 12.0%), decode in every browser, and are
where the practical savings live. The three formats price the per-file costs very
differently: a JPEG file carries roughly 600 bytes of Huffman and quantization table
definitions plus headers, a PNG a 67-byte structural floor plus per-image filter
adaptation, and a WebP as little as 30 bytes of container around a heavily
image-adapted VP8 payload. This report quantifies what bundling recovers, per codec,
tile size, and image count, under a matched-quality protocol, and describes a testbed
that measures the timing consequences under HTTP/1.1, HTTP/2, and HTTP/3.</p>
<p>The display side needs no special machinery: a bundled tile is shown by any of CSS
<code>background-position</code> (universal), <code>object-view-box</code> (Chromium),
canvas <code>drawImage</code> region blits, or SVG <code>viewBox</code> cropping. The
browser decodes the atlas once and paints windows into it.</p>

<h2>2&nbsp;&nbsp;Related work</h2>
<p>Bundling under HTTP/2 has been measured for JavaScript: Khan Academy found unbundled
JS slower than bundles under HTTP/2, attributing the gap to worse per-file compression
[1]. For images, a CSS-Tricks icon case study reports a 223-icon sprite at roughly 10 KB
versus 115 KB unbundled [2], without protocol timing. Academic HTTP/2 and HTTP/3 studies
measure whole-page loads and server push [3, 4]; HTTP/3 outperforms HTTP/2 markedly
under packet loss [5]. Container-overhead floors per format are documented via minimal
1x1-pixel files: JPEG&nbsp;XL 24 B, WebP 30 B, PNG 67 B, JPEG 155 B, AVIF 303 B [6, 7].
HTTP Archive's 2024 Media chapter establishes the prevalence of the many-small-images
regime [8]. No published measurement quantifies image atlasing under HTTP/2 or HTTP/3,
and no codec-by-tile-size atlasing sweep at matched quality exists; texture-atlas
practice in game engines addresses GPU sampling, not codec efficiency [9].</p>

<h2>3&nbsp;&nbsp;The atlas serving model</h2>
<h3>3.1&nbsp;&nbsp;Rendering a tile from an atlas in HTML</h3>
<p>A bundled page references one image resource and displays each tile by cropping a
window into it. Four standard mechanisms cover every deployment context. The classic and
universal one positions the atlas behind a fixed-size element as a background:</p>
<pre>&lt;div class="tile" style="background-image:url(atlas.webp);
     background-position:-144px -216px"&gt;&lt;/div&gt;
/* .tile has width:72px; height:72px */</pre>
<p>The element shows the 72x72 region whose top-left corner sits at (144,&nbsp;216);
<code>background-size</code> rescales the whole atlas when display size differs from
stored size. Chromium additionally supports cropping a real <code>&lt;img&gt;</code>
element, which preserves alt text, native lazy loading, and
<code>fetchpriority</code>:</p>
<pre>&lt;img src="atlas.webp" style="width:72px;height:72px;
     object-view-box:xywh(144px 216px 72px 72px)"&gt;</pre>
<p>Where a real image element is needed cross-browser, a fixed-size wrapper with
<code>overflow:hidden</code> around a negatively-offset <code>&lt;img&gt;</code> gives
the same window, and SVG gives it declaratively
(<code>&lt;svg viewBox="144 216 72 72"&gt;&lt;image href="atlas.webp"/&gt;</code>).
Canvas completes the set for programmatic UIs:
<code>ctx.drawImage(atlas, 144, 216, 72, 72, dx, dy, 72, 72)</code> blits any region
after a single decode. In every mechanism the browser fetches and decodes the atlas
once, holds one decoded copy, and paints windows into it; per-tile cost is a paint, not
a decode. The experiments in Section&nbsp;6 use <code>background-position</code>, the
mechanism with universal support.</p>
<h3>3.2&nbsp;&nbsp;Delivery, caching, and memory</h3>
<p>An atlas changes the unit of caching from the tile to the bundle. With standard
immutable content-addressed URLs (<code>atlas.3fe2a1.webp</code>,
<code>Cache-Control: immutable</code>), an unchanged atlas costs zero requests on a warm
cache, and the decode-once property still applies. The cost appears on content change:
editing one tile invalidates the whole bundle, so the expected re-download per deploy
grows with bundle size. Splitting the collection into k chunked atlases bounds this
blast radius at 1/k of the collection while retaining nearly all of the byte and
request savings (Section&nbsp;5, Table&nbsp;1: four chunks price within one percentage
point of one atlas), which makes chunking the practical default for collections that
update piecemeal. Grouping tiles by update cadence (stable icon set in one chunk,
weekly seasonal art in another) further confines invalidation to the chunk that
actually changed.</p>
<p>The second resource to budget is decoded memory: a decoded atlas occupies
width&nbsp;x&nbsp;height&nbsp;x&nbsp;4 bytes regardless of its encoded size, so a
4096x4096 atlas holds 64&nbsp;MB of RGBA for a 300&nbsp;KB transfer. Individual images
decode lazily and can be evicted per tile; an atlas is decoded and resident as a unit
while any tile is visible. Chunking bounds this cost the same way it bounds
invalidation, and below-the-fold chunks combine with lazy loading so off-screen tiles
cost neither bytes nor memory.</p>

<h2>4&nbsp;&nbsp;Measurement method</h2>
<h3>4.1&nbsp;&nbsp;Assets and packing</h3>
<p>Two deterministic asset classes: 520 Twemoji 72x72 flat-art tiles (alpha composited
over white) and 520 photographic 224x224 thumbnails. Tiles are packed row-major into a
near-square grid; a padding variant edge-replicates each tile by 8 or 16 pixels. All
conditions consume identical source pixels.</p>
<h3>4.2&nbsp;&nbsp;Codecs and matched-quality protocol</h3>
<p>Following the study's scope, the three dominant web formats encode each condition:
libjpeg-turbo JPEG, WebP (lossy and lossless), and PNG, with the lossy codecs swept
over a quality ladder q &isin; {{30,50,65,80,90}}. Per-tile quality is measured as luma SSIM after cropping the tile
back out of the decoded artifact, so atlas border bleed is charged to the atlas. Bytes
are compared at equal quality by log-linear interpolation of each condition's
rate-distortion curve at fixed SSIM targets; when an atlas's entire ladder exceeds the
target, its cheapest measured point is used, understating the atlas's advantage, and the
value is reported as a lower bound. Three invariants validate the harness: lossless
conditions score SSIM exactly 1.0; an atlas of one image is byte-identical to the
individual file; padding never reduces atlas bytes.</p>

<h2>5&nbsp;&nbsp;Static results: bytes at matched quality</h2>
{fig_atlas}
<p>Table 1 reports the saving from atlasing at SSIM 0.97 across both classes. Three
regularities organize the table. First, savings scale with the ratio of per-file
structural cost to content bytes: 72-pixel flat-art tiles encode to 1&ndash;3 KB, so
JPEG's roughly 600 bytes of per-file tables and headers alone account for most of its
measured 26&ndash;34% saving, while WebP's 30-byte floor leaves it the smallest lossy
gain (8&ndash;17%). Second, savings grow with N and saturate near N&nbsp;=&nbsp;200:
amortization is essentially complete once hundreds of per-file overheads collapse into
one. Third, the same 500 tiles that save 26% under JPEG at 72 pixels save 3% at 224
pixels: tile size, not image count, is the dominant variable.</p>
{table1}
{fig_bars}
<p>Atlasing is not free where per-image adaptation matters. Both lossless formats lose
from atlasing at N&nbsp;&ge;&nbsp;200 (PNG &minus;3 to &minus;6%, lossless WebP &minus;4
to &minus;5%): PNG chooses its prediction filter per scanline and an atlas scanline
crosses dozens of unrelated tiles, while lossless WebP fits transforms and entropy
codes per image, and one global model over hundreds of heterogeneous tiles cannot match
hundreds of specialized ones. Lossy WebP shows the same inversion on photographic tiles
(&minus;8.5% at N&nbsp;=&nbsp;500): VP8 adapts entropy tables per image and allows at
most four quantizer segments per frame, so an atlas of 500 diverse photos shares four
segments where individual files had four each; the raw byte cost is near zero, and the
penalty appears as reduced per-tile quality that the matched-quality protocol correctly
prices as bytes. Edge-replicated padding costs roughly 7 percentage points of saving
per 8-pixel step for JPEG and roughly 10 for WebP (flat art, N&nbsp;=&nbsp;200),
pricing the block-alignment mitigations against chroma bleed.</p>
{fig_charts}
<p>The absolute comparison compounds codec choice with bundling: at N&nbsp;=&nbsp;500
and SSIM 0.97 on flat art, individual JPEG files cost 630 KB, the JPEG atlas 464 KB,
individual WebP files 240 KB, and the WebP atlas 220 KB. Moving a legacy
individual-JPEG deployment to a WebP atlas cuts bytes by 65%; the format change
contributes most of it, and bundling contributes the rest while also collapsing 500
requests into one.</p>

<h2>6&nbsp;&nbsp;Network study design</h2>
<p>Byte savings are protocol-independent; timing effects are not. The companion testbed
serves both conditions from a Caddy server inside WSL2 with three protocol endpoints
(HTTP/1.1, HTTP/2, HTTP/3 on QUIC), shapes real packets with <code>tc netem</code>
(delay, bandwidth, random loss applied on the server egress), and drives a fresh
cold-cache Chromium instance per page load via Playwright. Each page stamps a
timestamp after every tile is decoded and two animation frames have painted, giving a
single time-to-all-tiles-visible endpoint, and records per-resource transfer sizes and
the negotiated protocol from the Resource Timing API, which also verifies that every
load used the intended protocol. The sweep crosses condition (individual, one atlas,
four chunked atlases) with N &isin; {{10, 50, 200, 500}}, both asset classes, three
protocols, and five network profiles (localhost floor; 100 Mbit/20 ms; 9 Mbit/60 ms;
1.6 Mbit/150 ms; 9 Mbit/60 ms with 1% loss), eight cold loads per cell. Results are
reported in the next revision of this report.</p>

<h2>7&nbsp;&nbsp;Toward optimal atlas construction</h2>
<p>The preceding sections treat bundling as a binary choice. The general problem is an
optimization: given images i with encoded sizes s<sub>i</sub>, content class
c<sub>i</sub>, update probability p<sub>i</sub> per deploy, and viewport visibility
v<sub>i</sub>, choose a partition of the set into bundles B<sub>1</sub>..B<sub>k</sub>,
a tile ordering within each bundle, and a codec per bundle, minimizing</p>
<p style="text-align:center;text-indent:0">J = w<sub>b</sub>&nbsp;E[bytes per deploy] +
w<sub>t</sub>&nbsp;latency(k; protocol, network) + w<sub>m</sub>&nbsp;peak decoded
memory,</p>
<p style="text-indent:0">subject to a per-tile quality floor, where
E[bytes]&nbsp;=&nbsp;&Sigma;<sub>j</sub>&nbsp;[1&nbsp;&minus;&nbsp;&Pi;<sub>i&isin;B<sub>j</sub></sub>(1&nbsp;&minus;&nbsp;p<sub>i</sub>)]&nbsp;&middot;&nbsp;bytes(B<sub>j</sub>)
prices whole-bundle cache invalidation. The measured curves of Sections&nbsp;5
and&nbsp;6 supply the byte and latency terms; three further measurements calibrate the
remaining degrees of freedom. First, within-bundle tile ordering: packing visually
similar tiles adjacently changes what the codec's spatial context can exploit, and is
evaluated by re-encoding identical tile sets under filename, random, luminance-sorted,
mean-color-sorted, cluster-grouped, and greedy nearest-neighbor orders. Second, the
chunk count k trades overhead amortization against invalidation blast radius and
parallelism; J(k) is measured directly on the testbed. Third, cadence grouping assigns
tiles with correlated update probabilities to the same bundle, which lowers E[bytes]
at fixed k. The deliverable is an atlas-optimizer tool that takes a directory of
images with a manifest of update rates and quality targets and emits the partition,
per-bundle codec, atlas files, and CSS coordinate map.</p>

<h2>8&nbsp;&nbsp;Practical guidance</h2>
<p>The static study supports a codec-aware bundling rule for the deployed-everywhere
formats. Atlas small lossy assets: icon-class tiles gain 26&ndash;34% at matched
quality under JPEG and 8&ndash;17% under WebP, and the WebP atlas is the smallest
absolute payload. Do not atlas lossless assets (PNG, lossless WebP): per-image
adaptation beats the shared context, and the loss grows with N. Do not atlas
200-pixel-class photographs for byte reasons: the JPEG saving is a few percent and
WebP inverts; whether the request-count reduction pays on latency is a protocol
question, not a compression question. Pack without padding unless measured chroma
bleed on the target content demands alignment, and price that padding at roughly
7&ndash;10 points of saving per 8 pixels.</p>

<h2 class="refs-head">References</h2>
<div class="refs">
<p>[1] C. Johnson. Forgo JS packaging? Not so fast. Khan Academy Engineering, 2015.
https://blog.khanacademy.org/forgo-js-packaging-not-so-fast/</p>
<p>[2] C. Coyier. Musings on HTTP/2 and bundling. CSS-Tricks.
https://css-tricks.com/musings-on-http2-and-bundling/</p>
<p>[3] M. Varvello et al. Is the Web HTTP/2 yet? PAM 2016.</p>
<p>[4] S. R. Dahal et al. HTTP/2 server push: a performance study. arXiv:2207.05885.</p>
<p>[5] T. Hunter. HTTP/3 is fast. Request Metrics, 2022.
https://requestmetrics.com/web-performance/http3-is-fast/</p>
<p>[6] T. Eden. What's the smallest file size for a 1 pixel image? 2024.
https://shkspr.mobi/blog/2024/01/whats-the-smallest-file-size-for-a-1-pixel-image/</p>
<p>[7] J. Sneyers. One pixel is worth three thousand words. Cloudinary Blog.
https://cloudinary.com/blog/one_pixel_is_worth_three_thousand_words</p>
<p>[8] HTTP Archive. Web Almanac 2024, Media chapter.
https://almanac.httparchive.org/en/2024/media</p>
<p>[9] Unity Technologies. Sprites.AtlasSettings.paddingPower documentation.
https://docs.unity3d.com/ScriptReference/Sprites.AtlasSettings-paddingPower.html</p>
</div>
<div class="footer">Alexander Apartsin &middot; original project MPCode 2001 &middot; revisited 2026</div>
</body></html>"""

    out = ROOT / "docs" / "paper.html"
    out.write_text(html, encoding="utf-8")
    # the paper IS the site landing page
    (ROOT / "docs" / "index.html").write_text(html, encoding="utf-8")
    # content canaries
    for canary in ["Table 1.", "Figure 1.", "Figure 2.", "Figure 3.", "<svg",
                   "atlas_emoji_100.png", "Abstract", "References",
                   "background-position", "object-view-box", "Cache-Control"]:
        assert canary in html, f"CANARY FAILED: {canary}"
    assert html.count("<svg") >= 4, "CANARY FAILED: expected 4 charts"
    assert html.count("aria-label") >= 4, "CANARY FAILED: chart accessibility labels"
    print(f"wrote {out} ({len(html):,} bytes), canaries pass")


if __name__ == "__main__":
    main()
