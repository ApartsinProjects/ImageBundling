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


def icon_table():
    f = ROOT / "results" / "static" / "e_icons" / "results.json"
    if not f.exists():
        return ""
    rows = json.load(f.open())
    order = [("__individual_ll", "individual WebP-lossless files (baseline)"),
             ("webpll_strip", "WebP-lossless strip"),
             ("png_strip_shared_palette", "PNG shared-palette strip"),
             ("png_strip_rgba", "PNG strip (RGBA)"),
             ("webpll_grid", "WebP-lossless grid"),
             ("jpeg_grid_atlas_ssim97", "JPEG atlas (matched SSIM 0.97)")]
    # baseline: back out individual WebP-lossless bytes from the strip saving_pct
    base = {}
    for x in rows:
        if x["cond"] == "webpll_strip":
            base[(x["corpus"], x["size"])] = round(x["bytes"] / (1 - x["saving_pct"] / 100))
    trows = []
    for cond, label in order:
        cells = []
        for corpus in ("clean", "dup"):
            for size in (24, 48):
                if cond == "__individual_ll":
                    v = base.get((corpus, size))
                    cells.append(f"<td>{v:,}</td>" if v else "<td>&mdash;</td>")
                    continue
                r = next((x for x in rows if x["cond"] == cond and
                          x["corpus"] == corpus and x["size"] == size), None)
                cells.append(f"<td>{r['bytes']:,}</td>" if r else "<td>&mdash;</td>")
        trows.append(f"<tr><td>{label}</td>{''.join(cells)}</tr>")
    return ("<div class='tablewrap'><table>"
            "<caption><b>Table 3.</b> Bundle bytes for 200 synthetic flat icons (fixed "
            "12-color palette, alpha), lossless unless noted, on a clean corpus and one "
            "with 20% exact + 20% near-duplicate tiles. Lossless bundles are byte-exact "
            "(palette conversion verified identical after decode); the JPEG row is the "
            "matched-SSIM-0.97 grid atlas. Smaller is better.</caption>"
            "<thead><tr><th>bundle</th><th>clean 24px</th><th>clean 48px</th>"
            "<th>dup 24px</th><th>dup 48px</th></tr></thead>"
            f"<tbody>{''.join(trows)}</tbody></table></div>")


def warmcache_table():
    f = ROOT / "results" / "static" / "e_warmcache" / "results.json"
    if not f.exists():
        return ""
    d = json.load(f.open())
    cols = [("individual", "individual"), ("atlas1", "1 atlas"),
            ("atlas4", "4 chunks"), ("atlas16", "16 chunks"),
            ("bytebundle4", "byte-bundle x4"), ("dict_delta", "dict-delta")]
    trows = []
    for r in d["rows"]:
        cells = "".join(f"<td>{r[k]:,}</td>" for k, _ in cols)
        trows.append(f"<tr><td>{r['churn_pct']:.0f}%</td><td>{r['tiles_changed']}</td>{cells}</tr>")
    return ("<div class='tablewrap'><table>"
            "<caption><b>Table 4.</b> Warm-cache re-download: bytes a returning client "
            "must fetch after a deploy changes a fraction of a 200-tile WebP collection "
            f"(full fresh download {d['total_fresh_download']:,} B), by serving strategy, "
            "mean of 20 random deploys per churn rate. Immutable individual files fetch "
            "only changed tiles; a monolithic atlas re-fetches everything on any change; "
            "dictionary-delta serving tracks the individual-file optimum and beats it at "
            "high churn.</caption>"
            "<thead><tr><th>churn</th><th>tiles</th><th>individual</th><th>1 atlas</th>"
            "<th>4 chunks</th><th>16 chunks</th><th>byte-bundle x4</th><th>dict-delta</th>"
            f"</tr></thead><tbody>{''.join(trows)}</tbody></table></div>")


def load_network(tag="phase2v3"):
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
                ("cell4g", "9 Mbit / 60 ms"), ("lossy4g", "9 Mbit / 60 ms / 1% loss")]
    trows = []
    for cls, clabel in [("emoji", "flat art"), ("photos", "photos")]:
        for pkey, plabel in profiles:
            for proto in ["h1", "h2", "h3"]:
                i = med.get((pkey, proto, cls, 500, "individual"))
                a1 = med.get((pkey, proto, cls, 500, "atlas1"))
                a4 = med.get((pkey, proto, cls, 500, "atlas4"))
                bb = med.get((pkey, proto, cls, 500, "bundlebin"))
                if not (i and a1):
                    continue
                trows.append(
                    f"<tr><td>{clabel}</td><td>{plabel}</td><td>{proto}</td>"
                    f"<td>{i:,.0f}</td><td>{a1:,.0f}</td>"
                    f"<td>{a4:,.0f}</td><td>{bb:,.0f}</td>"
                    f"<td><b>{i/a1:.1f}x</b></td><td>{i/bb:.1f}x</td></tr>")
    table2 = ("<div class='tablewrap'><table>"
              "<caption><b>Table 2.</b> Median time to all 500 tiles visible (ms) per "
              "serving condition, protocol, and network profile (n&nbsp;=&nbsp;7 cold "
              "browser loads per cell, first load dropped; WebP payloads). These are "
              "medians without confidence intervals; per-cell quartiles are in the "
              "released data. The atl-x and bun-x columns give the speedup of the single "
              "atlas and of the byte-bundle relative to individual files (individual "
              "median divided by condition median).</caption>"
              "<thead><tr><th>class</th><th>network</th><th>proto</th>"
              "<th>individual</th><th>atlas</th><th>atlas x4</th><th>byte-bundle</th>"
              "<th>atl-x</th><th>bun-x</th></tr></thead>"
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
            "atlasing (median individual / median single atlas) at N&nbsp;=&nbsp;500, "
            "per protocol and network profile. The dashed line marks parity. HTTP/2 "
            "narrows the gap furthest; HTTP/1.1 and HTTP/3 leave multi-x speedups on "
            "the table for small flat tiles.</figcaption></figure>")
    return table2 + fig4


def main():
    rows = (load("phase1_emoji") + load("phase1_photos") +
            load("phase1_photos112") + load("phase1_photos56"))
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
    for cls, label in [("emoji", "flat art 72px"), ("photos56", "photos 56px"),
                       ("photos112", "photos 112px"), ("photos", "photos 224px")]:
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
                 f"{emoji_ex['atlas_px']}px). Encoded with identical encoder settings both ways (distinct from Table&nbsp;1's matched-quality protocol), the "
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

    net_html = network_results_html()
    icon_html = icon_table()
    warm_html = warmcache_table()

    _sec, _sub = [0], [0]

    def H2(t):
        _sec[0] += 1
        _sub[0] = 0
        return f'<h2>{_sec[0]}&nbsp;&nbsp;{t}</h2>'

    def H3(t):
        _sub[0] += 1
        return f'<h3>{_sec[0]}.{_sub[0]}&nbsp;&nbsp;{t}</h3>'

    html = f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Image Bundling Revisited</title><style>{CSS}</style></head><body>
<h1>Image Bundling Revisited: Atlasing Small Web Images under Modern Codecs and
Protocols</h1>
<div class="authors">Alexander Apartsin</div>
<div class="venue">Technical Report &middot; 2026</div>

<div class="abstract"><div class="ahead">Abstract</div>
<p>Web pages routinely load tens to hundreds of small images; the median mobile page
carries 13 image elements and the 90th percentile carries 56. Serving each image as a
separate resource pays three costs: per-request protocol overhead, a fixed per-file
structural cost (headers, coding tables, container chunks; roughly 600 bytes for a
JPEG), and the loss of cross-image redundancy that a codec can exploit only within one
file. This report measures how much of these costs bundling recovers when many small
images are packed into a single atlas image and displayed with standard CSS. The study
focuses on the three formats that carry the overwhelming majority of web images today
and decode in every browser: JPEG, PNG, and WebP. At matched per-tile quality (structural similarity, SSIM, where 1.0 is a
pixel-exact match; target 0.97), atlasing 72-pixel flat-art tiles saves up to 26% of bytes under JPEG and up to 15%
under WebP at matched quality, and the saving is protocol-independent. The saving is governed
by the ratio of per-file structural cost to content bytes, and the photographic
size sweep traces the crossover: 56-pixel thumbnails save 29.8% (JPEG) and 15.3%
(WebP), 112-pixel thumbnails 9.8% and &minus;1.4%, and 224-pixel thumbnails 3.0% and
&minus;8.5%, with grid-atlased lossless formats inverting into a cost wherever
per-scanline or per-image adaptation outperforms a single global model. These
measurements yield a codec- and layout-aware bundling rule: grid-atlas small lossy
tiles, and do not grid-atlas heterogeneous lossless or large photographic tiles;
crucially, the same lossless assets that lose under a grid win by 40&ndash;95% under
codec-aware packing (vertical strips, shared palettes), so the rule is about how to
pack, not a blanket prohibition. Beyond the binary decision, the report treats atlas
construction as a cost to minimize, bytes per deploy under cache invalidation, load
latency for the target protocol and network, and decoded memory, subject to a per-tile
quality floor, and calibrates a heuristic that navigates it. An ordering-and-partition study calibrates the heuristic's levers: cluster-pure
bundles save 3 percentage points for lossless flat art, and for collections with
repeated tiles, a similarity-sorted atlas dedupes copies inside the codec's matching
window, cutting PNG bytes by 17&ndash;18% at a 21.6% duplicate rate, a saving
separately-served files cannot reach on any protocol. A network study over 2,515 validated
cold loads across HTTP/1.1, HTTP/2, and HTTP/3 under emulated network conditions
completes the picture: bundling 500 flat tiles is 7&ndash;9x faster to full visibility
on HTTP/1.1 and 4&ndash;8x on HTTP/3, while HTTP/2's multiplexing closes most of the
latency gap and leaves bundling there as chiefly a byte optimization; under packet
loss, chunked atlases outperform one large atlas by spreading the transfer across
connections.</p></div>

{H2('Introduction')}
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
definitions plus headers, a PNG a 67-byte structural floor plus per-scanline filter
adaptation, and a WebP as little as 30 bytes of container around a heavily
image-adapted VP8 payload. This report quantifies what bundling recovers, per codec,
tile size, and image count, under a matched-quality protocol, and describes a testbed
that measures the timing consequences under HTTP/1.1, HTTP/2, and HTTP/3.</p>
<p>The regimes this study measures map onto concrete page types. Product grids and
image-search results serve 100&ndash;280-pixel photographic thumbnails by the dozens;
recommendation strips, cart previews, and avatar rows serve 48&ndash;96-pixel photos;
emoji and reaction pickers serve 24&ndash;64-pixel flat art by the hundreds, and are
one place where sprite atlases remain in production use today (chat applications ship
emoji sheets; video platforms ship hover-preview storyboards as frame mosaics). The
tile-size axis of the experiments spans exactly this range, so each regime can read
its expected saving off the measured curves.</p>
<p>The display side needs no special machinery: a bundled tile is shown by any of CSS
<code>background-position</code> (universal), <code>object-view-box</code> (Chromium),
canvas <code>drawImage</code> region blits, or SVG <code>viewBox</code> cropping. The
browser decodes the atlas once and paints windows into it.</p>
<p><b>Contributions.</b> This report contributes (i) a matched-quality sweep of
image atlasing across the three universally-supported web codecs, which we believe is
the first to appear in the peer-reviewed literature, (JPEG, PNG, WebP) over
tile size and image count, establishing that the byte saving is governed by the ratio
of per-file structural cost to content bytes; (ii) a network study of 2,515 validated
cold browser loads that separates the timing effect of bundling across HTTP/1.1,
HTTP/2, and HTTP/3 under emulated network conditions; (iii) a set of construction
techniques with measured effect, PNG vertical-strip packing, explicit and LZ-window
duplicate exploitation, chunking for loss resilience, delta updates via compression
dictionaries, and encoder-parameter tuning that flips WebP's photographic-atlas penalty
to a gain; (iv) a coupling-spectrum account that unifies the results, savings arise from
sharing fixed costs and losses from sharing adaptive state; and (v) an open-source
construction heuristic that emits deployable bundles from a directory of images.</p>

{H2('Related work')}
{H3('Sprites, bundling, and HTTP multiplexing')}
<p>Combining many small resources into one is long-standing web practice; CSS sprites
[10] and the DataURI/inlining family traded requests for cache granularity in the
HTTP/1.1 era. Whether bundling still pays under HTTP/2 multiplexing has been examined
mainly for JavaScript and CSS: Khan Academy found unbundled JS slower than bundles under
HTTP/2, attributing the gap to worse per-file compression [1], and practitioner analyses
reach the same conclusion for concatenated assets [2, 11]. The closest academic work is
Marx et al. [29], who test concatenation, embedding, and sharding under HTTP/2 and find
the HTTP/1 packaging habits still often help; broader page-load studies show load time
is governed by resource dependencies and compute, not bytes alone (WProf [26], How
Speedy is SPDY? [27], Polaris [28]), so request-count reductions are only part of the
story. For images specifically, a
CSS-Tricks case study reports a 223-icon sprite at roughly 10&nbsp;KB versus 115&nbsp;KB
unbundled [2], but without protocol-level timing. We find no published measurement that
quantifies image atlasing under HTTP/2 or HTTP/3, nor a codec-by-tile-size atlasing
sweep at matched quality.</p>
{H3('Protocol performance: HTTP/2 and HTTP/3')}
<p>HTTP/2 multiplexes many requests over one connection [12] but suffers transport-level
head-of-line blocking under loss; HTTP/3 over QUIC [13] removes it with per-stream
recovery. Measurement studies characterize HTTP/2 adoption and page-load behavior
[3] and server push [4], and both controlled benchmarks [5] and adoption studies [14]
report HTTP/3 gaining most under packet loss while sitting near parity at zero loss.
Domain sharding, the historical technique of spreading resources across hosts to widen
HTTP/1.1 concurrency [15], is the opposite of bundling; recent measurement finds such
HTTP/1-era habits persist even under HTTP/2 [30], which motivates our condition set. None of this work isolates a many-small-images payload against a bundled
baseline.</p>
{H3('Codec container overhead and small-image efficiency')}
<p>The fixed per-file cost each codec carries is documented through minimal one-pixel
files: JPEG&nbsp;XL 24&nbsp;B, WebP 30&nbsp;B, PNG 67&nbsp;B, JPEG 155&nbsp;B, AVIF
303&nbsp;B [6, 7]. This overhead makes small images the worst case for heavyweight
containers, and production pipelines act on it: Cloudinary declines AVIF for images
below 5,000 pixels because the box overhead outweighs the coding gain [16]. The JPEG
[17], PNG [18], and WebP [19] format definitions specify the table, chunk, and
container structures our measurements amortize, and peer-reviewed rate-distortion
studies compare these formats against newer codecs [31]. Perceptual image-quality
assessment, on which our matched-quality protocol rests, is grounded in the structural
similarity index [25]. We are not aware of prior work that
measures how bundling recovers this overhead as a function of codec and tile size.</p>
{H3('Texture atlases and dictionary compression')}
<p>Packing many images into one is standard in real-time graphics, where texture atlases
[9, 20, 32] and skyline/MaxRects bin-packing [21] minimize GPU state changes and padding is
tuned for mip-sampling rather than codec efficiency. On the delivery side, shared-window
and trained-dictionary compression (Brotli [22], zstd [23]) and Compression Dictionary
Transport [24] let an update be encoded against previously cached bytes; we apply the
last to the whole-bundle cache-invalidation problem. HTTP Archive's Web Almanac [8]
supplies the population statistics (median 13 images per mobile page, format share) that
make the many-small-images regime the common case rather than an edge case.</p>

{H2('The atlas serving model')}
{H3('Rendering a tile from an atlas in HTML')}
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
a decode. The experiments use <code>background-position</code>, the mechanism with
universal support.</p>
{H3('Delivery, caching, and memory')}
<p>An atlas changes the unit of caching from the tile to the bundle. With standard
immutable content-addressed URLs (<code>atlas.3fe2a1.webp</code>,
<code>Cache-Control: immutable</code>), an unchanged atlas costs zero requests on a warm
cache, and the decode-once property still applies. The cost appears on content change:
editing one tile invalidates the whole bundle, so the expected re-download per deploy
grows with bundle size. Splitting the collection into k chunked atlases bounds the
worst-case invalidation at 1/k of the collection while retaining nearly all of the byte and
request savings (Section&nbsp;5.1, Table&nbsp;1: four chunks price within one percentage
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

{H2('Methodology')}
{H3('Assets and packing')}
<p>Two deterministic asset classes anchor the study: 521 Twemoji 72x72 flat-art tiles
(alpha composited over white) and 521 photographic 224x224 thumbnails, with the photo
set additionally downscaled to 112 and 56 pixels for the size sweep and synthetic
icon, product-thumbnail, and avatar corpora added for the use-case tests
(Section&nbsp;5.4). Tiles are packed row-major into a near-square grid; a padding
variant edge-replicates each tile by 8 or 16 pixels, and a vertical-strip variant packs
one tile per row band. All conditions consume identical source pixels.</p>
{H3('Codecs and matched-quality protocol')}
<p>Following the study's scope, the three dominant web formats encode each condition:
libjpeg-turbo JPEG, WebP (lossy and lossless), and PNG, with the lossy codecs swept
over a quality ladder q &isin; {{30,50,65,80,90}}. Quality is the mean over tiles of the
per-tile luma SSIM [25], each tile scored after cropping it back out of the decoded artifact
so atlas border bleed is charged to the atlas; the matched target of 0.97 is therefore a
mean-tile floor, and Section&nbsp;5.4 reports the per-tile spread where it is
load-bearing. Bytes are compared at equal quality by log-linear interpolation of each
condition's rate-distortion curve at the target; the five-point ladder is coarse, so
where the atlas and individual curves nearly coincide the interpolation is unstable and
equal-quality byte comparison is used instead (Section&nbsp;5.4). When an atlas's entire
ladder exceeds the target, its cheapest measured point is used, understating the atlas's
advantage, and the value is reported as a lower bound. Three invariants validate the harness: lossless
conditions score SSIM exactly 1.0; an atlas of one image is byte-identical to the
individual file; padding never reduces atlas bytes.</p>
{H3('Network testbed')}
<p>Byte savings are protocol-independent; timing effects are not. The network testbed
serves every condition from a Caddy server inside WSL2 with three protocol endpoints
(HTTP/1.1, HTTP/2, HTTP/3 on QUIC), shapes real packets with <code>tc netem</code>
(delay, bandwidth, random loss applied on the server egress), and drives a fresh
cold-cache Chromium instance per page load via Playwright. Each page stamps a timestamp
after every tile is decoded and two animation frames have painted, giving a single
time-to-all-tiles-visible endpoint, and records per-resource transfer sizes and the
negotiated protocol from the Resource Timing API; every load is validated against the
intended protocol and against the manifest's byte totals, so a page that fetched the
wrong way cannot enter the dataset. Four serving conditions run: N individual files, one
atlas, four chunked atlases, and a byte-bundle (the N encoded files concatenated into
one binary resource plus an offset index; the client slices the buffer and decodes each
tile from its own bytes, retaining per-file codec adaptation while collapsing N requests
into one). The sweep crosses these with N&nbsp;&isin;&nbsp;{{50, 200, 500}}, both asset
classes as WebP q80, three protocols, and four network profiles, 2,515 validated cold
loads in total.</p>
{H3('Artifact availability')}
<p>All code, asset manifests, raw per-run measurements, and the construction heuristic
are released at <a href="https://github.com/ApartsinProjects/ImageBundling">github.com/ApartsinProjects/ImageBundling</a>,
and every table and figure in this report is regenerated from that data by a single
build command. The measurements use Pillow&nbsp;12.2 (libwebp&nbsp;1.6.0, libjpeg-turbo
via libjpeg&nbsp;8.0, zlib-ng&nbsp;1.3.1), Python&nbsp;3.14, zstandard and Brotli for the
delta-update study, Caddy&nbsp;2.11.4 for the three-protocol server, and Playwright&nbsp;1.58
driving Chromium&nbsp;145 for the network loads. The photographic corpus is drawn from
Lorem&nbsp;Picsum and the flat-art corpus from the Twemoji set; both frozen manifests are
in the repository so every condition consumes identical source pixels.</p>

{H2('Results')}
{H3('Byte savings at matched quality')}
{fig_atlas}
<p>Table 1 reports the saving from atlasing at SSIM 0.97 across both classes. Three
regularities organize the table. First, savings scale with the ratio of per-file
structural cost to content bytes: 72-pixel flat-art tiles encode to 1&ndash;3 KB, so
JPEG's roughly 600 bytes of per-file tables and headers alone account for most of its
measured 19&ndash;26% saving across N, while WebP's 30-byte floor leaves it the smallest
lossy gain (8&ndash;15%). Second, savings broadly increase with N and flatten by a few
hundred tiles as amortization completes (the trend is not strictly monotonic; because
each N draws one deterministic subset, small non-monotonicities such as WebP flat art
at 8.3/15.2/8.2% for N&nbsp;=&nbsp;50/200/500 reflect subset composition, not a scaling
law). Third, tile size, not image count, is the dominant variable, and the photo rows
of Table&nbsp;1 trace the full crossover: downscaling the same 500 photographs from
224 to 112 to 56 pixels moves the JPEG saving from 3.0% to 9.8% to 29.8%, and moves
WebP from &minus;8.5% through &minus;1.4% to +15.3%, placing WebP's bundling
break-even near 100-pixel tiles. Search-result and recommendation thumbnails
(48&ndash;120&nbsp;px) therefore sit squarely in the paying regime for both formats,
while product-grid images (200&nbsp;px and up) pay only under JPEG, and only a few
percent.</p>
{table1}
{fig_bars}
<p>Atlasing is not free where per-image adaptation matters. On flat art, both lossless
formats lose from atlasing at N&nbsp;&ge;&nbsp;200 (PNG &minus;3 to &minus;6%, lossless WebP &minus;4
to &minus;5%): PNG chooses its prediction filter per scanline and an atlas scanline
crosses dozens of unrelated tiles, while lossless WebP fits transforms and entropy
codes per image, and one global model over hundreds of heterogeneous tiles cannot match
hundreds of specialized ones. Lossy WebP shows the same inversion on photographic tiles
(&minus;8.5% at N&nbsp;=&nbsp;500): VP8 adapts entropy tables per image and allows at
most four quantizer segments per frame, so an atlas of 500 diverse photos shares four
segments where individual files had four each; the raw byte cost is near zero, and the
penalty appears as reduced per-tile quality that the matched-quality protocol prices as
bytes; Section&nbsp;5.5 shows that encoder tuning reverses this penalty. Edge-replicated padding costs roughly 7 percentage points of saving
per 8-pixel step for JPEG and roughly 10 for WebP (flat art, N&nbsp;=&nbsp;200),
pricing the block-alignment mitigations against chroma bleed.</p>
{fig_charts}
<p>The absolute comparison compounds codec choice with bundling: at N&nbsp;=&nbsp;500
and SSIM 0.97 on flat art, individual JPEG files cost 630 KB, the JPEG atlas 464 KB,
individual WebP files 240 KB, and the WebP atlas 220 KB. Moving a legacy
individual-JPEG deployment to a WebP atlas cuts bytes by 65%; the format change
contributes most of it, and bundling contributes the rest while also collapsing 500
requests into one.</p>

{H3('Network timing under HTTP/1.1, HTTP/2, and HTTP/3')}
{net_html}
<p>Three protocol-level facts organize Table&nbsp;2 and Figure&nbsp;4. First, on
HTTP/1.1 and HTTP/3, bundling remains a large timing win: 7&ndash;9x and 4&ndash;8x
respectively for 500 flat-art tiles, and 1.3&ndash;2.8x for photos, across every
network profile. Second, HTTP/2 is the strongest protocol for many small files: its
multiplexing loads 500 individual images almost as fast as the atlas on
bandwidth-limited links (1.0&ndash;1.1x at 9&nbsp;Mbit), so under HTTP/2 the case for
bundling small tiles rests chiefly on the byte saving of Table&nbsp;1 (up to 26% for
flat art) rather than on latency. Third, on this testbed HTTP/3's individual-file loads run 4&ndash;5x slower
than HTTP/2's on the same links, including at zero loss, and a concurrency diagnostic
locates the cause. The diagnostic reconstructs each request's in-flight interval from the Resource Timing
API and finds the peak number of simultaneous image requests: HTTP/2 sustained
13&ndash;14 at once while HTTP/3 sustained only 6, roughly half the parallelism, and the
slowdown tracks that gap. This is a QUIC stream-limit and
flow-control effect (quic-go/Caddy defaults plus Chromium's QUIC stream pacing), a
configuration property of the deployment, not an inherent property of HTTP/3, which also
multiplexes independent streams over one connection. A default HTTP/3 deployment can therefore under-multiplex a many-small-image page
relative to HTTP/2, which makes bundling valuable there. Chunking is
loss insurance:
under 1% packet loss on HTTP/1.1, the single 3.6&nbsp;MB photo atlas on one TCP
connection drops to 0.9x (a stall risk the byte study cannot see), while four chunks
restore 1.8x by spreading the transfer over parallel connections. The byte-bundle beats individual serving nearly everywhere on HTTP/1.1 and HTTP/3
(up to 5.7x) at exactly the individual conditions' byte cost, which makes it the
bundling method of choice for content whose pixels should not share a codec model
(photos, lossless assets); the pixel atlas remains faster where its byte savings
compound with the request savings.</p>

{H3('Ordering, duplicates, and layout')}
<p>We re-encode identical tile sets under eight within-atlas orders (source
order, three random shuffles, luminance-sorted, mean-color-sorted, k-means
cluster-grouped, greedy nearest-neighbor) and two 4-way partitions (random split vs
cluster-pure split), for every in-scope codec at N&nbsp;=&nbsp;500. Three calibrated
rules emerge. For lossy codecs, ordering is worth at most one percent: the placement
of tiles does not recover the shared-model penalty, so the heuristic can ignore order
for JPEG and lossy WebP and spend its freedom elsewhere. For lossless flat art, order
and partition are real levers: source order (which groups semantically related icons)
is already near-optimal, random shuffling costs 2&ndash;4%, and cluster-pure chunks
beat randomly-split chunks by 3&nbsp;percentage points (lossless WebP, PNG alike),
so same-family tiles belong in the same bundle. For PNG specifically, layout is
decisive: packing tiles as a one-tile-wide vertical strip lets the per-scanline
filters re-adapt at every tile boundary, turning the PNG flat-art atlas from 5.7%
larger than individual files (grid layout) to 8.7% smaller, and lifting the photo
atlas from &minus;5.2% (grid, deduplicated 224px photos) to parity. Strip packing is therefore the PNG packing rule
(chunked to respect browser image-dimension limits), while block-aligned cells are
not worth adopting for any codec: aligning 72-pixel tiles to 80-pixel cells costs
7% in bytes for a quality gain below measurement noise.</p>
<p>The largest partition-level effect belongs to collections containing repeated
tiles. Real product grids repeat thumbnails freely (variant images, placeholder art,
re-listed items); in a test set where 21.6% of tiles were exact repeats, a
similarity-sorted atlas cut PNG bytes by 17&ndash;18% and lossless WebP bytes by
15&ndash;16% relative to unsorted packing, turning both formats' atlas comparison
against individual files from negative to clearly positive (+16.9% and +11.5%). The
mechanism is windowed matching: sorting places copies within the codec's LZ window,
which dedupes them. Exactly-identical tiles are already handled on the web by
content-addressed URLs (the browser fetches one copy and many elements reuse it), so
the atlas's unique contribution here is compressing near-duplicates: variant and recolored tiles that share most but not all pixels, which per-URL caching cannot merge.
The gain applies precisely to the LZ-class codecs and scales with the duplicate rate,
so the heuristic prices it as a measured dup-rate term: deduplicate exactly-repeated
tiles at the coordinate-map level (many CSS entries, one atlas region), and sort
near-duplicates adjacent so the encoder captures the rest.</p>
{H3('Winning content classes: icons, thumbnails, avatars')}
<p>The largest bundling wins in the whole study belong to lossless flat art, the
content of design-system icon sets, map-marker sprites, and flag pickers. On 200
synthetic flat icons with a small shared palette and alpha (Table&nbsp;3), a
WebP-lossless vertical-strip atlas is the smallest option at every size, 42&ndash;68%
below individual files and <b>7.6x smaller than the matched-quality JPEG atlas</b>. A lossless bundle beats the best lossy one outright, because JPEG must spend heavily to
avoid ringing on hard edges while the lossless codecs are both smaller and pixel-exact.
A shared-palette PNG (one pooled palette across the strip, verified byte-identical after
decode) wins 90&ndash;97% over individual paletted PNGs when the pooled palette fits,
and remains 4.9x smaller than the JPEG atlas. Strip layout beats grid for WebP-lossless
at both sizes, and the duplicate-heavy corpus widens the WebP-lossless strip win from
60% to 68% as the LZ window folds repeats. Two boundaries scope this result: the fixed
12-color corpus is the ideal case for shared palettes, so anti-aliased real icons with
hundreds of colors will see a smaller palette win (WebP-lossless, which does not depend
on palette size, is the robust default there); and for these alpha-bearing assets JPEG
is structurally disqualified, so the operative comparison is PNG versus WebP, both of
which the strip atlas improves.</p>
{icon_html}
<p>Two further use cases confirm where WebP wins on realistic content. Product-catalog
thumbnails, which sit on white backgrounds, bundle far better than the generic
full-frame photos of Section&nbsp;5.1: at equal WebP quality (per-tile SSIM matched within
0.006) a 100-thumbnail atlas saves 17.8% at 48&nbsp;px, 14.0% at 64&nbsp;px, and still
6.7% at 112&nbsp;px, all positive, because the homogeneous white field nearly removes
the shared-segment penalty that drives generic photos negative. Avatar walls add the
duplicate dimension: a comment thread of 200 slots drawn from a heavy-tailed popularity
distribution resolves to about 45 unique faces, and an atlas of the uniques (with many
coordinate-map entries pointing at repeats) saves 26% under WebP and 50% under JPEG at
32&nbsp;px versus serving the unique files individually. The lossy codecs do not
recover the duplication on their own, an atlas of all 200 slots is 5.0x the size of the
unique atlas, so deduplication must be explicit at the coordinate-map level. A
methodological note accompanies these: when the atlas and individual arms reach nearly
identical per-tile quality, as they do on homogeneous thumbnails, matched-SSIM byte
interpolation becomes unstable and equal-quality byte comparison is the reliable
measurement.</p>
{H3('Encoder parameters')}
<p>The photographic WebP penalty is not structural. VP8's default encode shares one set
of entropy tables and at most four quantizer segments across the whole atlas, and no
parameter raises the four-segment ceiling. But two efficiency controls, spatial noise
shaping at full strength and adaptive deblocking (autofilter), together move a
120-tile 224-pixel photo atlas from &minus;9.0% to <b>+5.0%</b> against individual
files at matched SSIM. An equal-quality check isolates the mechanism: with the advanced
settings the atlas reaches per-tile SSIM 0.980, above the individual files' 0.979,
while encoding 2.4% fewer bytes, because adaptive deblocking removes the block artifacts
that the atlas's internal tile-grid boundaries introduce and noise shaping exploits the
larger frame's masking context. The knobs improve both arms, but they help the atlas
more, so the earlier negative for WebP photographs holds only for the default encoder,
not for a tuned one. These controls are reachable through libwebp's configuration
(the <code>cwebp -sns 100 -pass 10 -af</code> equivalents) though not through every
image library's default binding.</p>

{H2('Discussion')}
{H3('The coupling spectrum')}
<p>The results organize on a single axis: what a set of tiles is made to share. At one
end, the byte-bundle shares only transport: it concatenates independently-encoded files,
so it never costs bytes and never gains cross-image compression. Two standard-container
formats sit at the same point, JPEG abbreviated format (one shared table datastream plus
per-tile table-less scans) and animated WebP (one independent payload per frame), both
measured byte-equivalent to the byte-bundle while offering a playable container or
per-tile random access. A shared-table bundle adds table sharing; the pixel atlas goes furthest,
sharing the entire coding model, palette, entropy context, quantizer segments, and
filters. The measurements then reduce to one principle: bundling <em>saves</em> to the
extent tiles share <em>fixed</em> costs (container overhead, tables, duplicate content),
and <em>loses</em> to the extent they are forced to share <em>adaptive</em> state (a
single quantizer allocation, one scanline-filter prediction context, one palette) that individually-encoded
files would have specialized. Every measured sign follows: JPEG always wins because its
shared cost (tables) is large and its adaptive coupling is weak; lossless flat art wins
hugely because a shared palette is pure fixed-cost saving; photographic WebP loses under
the default encoder because the shared four-segment allocation is adaptive state, and
recovers once adaptive deblocking neutralizes the artifact that sharing introduced.</p>
<p>The spectrum has a hard end. Individual serving costs
&Sigma;<sub>i</sub>&nbsp;(H<sub>i</sub>&nbsp;+&nbsp;C<sub>i</sub>(x<sub>i</sub>)), where
H<sub>i</sub> is a file's fixed overhead and C<sub>i</sub> its compressed payload under
state tuned to that image; an atlas costs
H&nbsp;+&nbsp;C(x<sub>1</sub>..x<sub>N</sub>;&thinsp;&theta;) with one shared header and
one shared adaptive state &theta;. Bundling wins only when the saved overhead
&Sigma;<sub>i</sub>&nbsp;H<sub>i</sub>&nbsp;&minus;&nbsp;H exceeds the cost of replacing
each image's optimal state by the shared &theta;. For large, unrelated photographs
H<sub>i</sub>/C<sub>i</sub>&nbsp;&rarr;&nbsp;0: almost no fixed overhead remains to
amortize while any adaptation penalty persists, so a single browser-decodable pixel
atlas is not expected to beat independently-optimized files for a sufficiently large,
heterogeneous photographic corpus. This is the
boundary the measurements trace, JPEG's advantage falling from +30% at 56&nbsp;px to +3%
at 224&nbsp;px, and it is why the byte-bundle, which shares only transport, is the
principled zero-coupling endpoint rather than a fallback. The open direction is to
decouple adaptation spatially while keeping single-resource amortization: WebP's lossless
format already carries a spatially-varying entropy image (meta-prefix groups), and
aligning that grid to atlas tile boundaries, which today requires instrumenting the
encoder, is the most promising route to a lossless photographic atlas that wins on
bytes.</p>
{H3('Cache invalidation and delta updates')}
<p>Bundling's one structural liability is cache granularity: editing a single tile
invalidates the whole bundle, so a naive re-deploy re-downloads everything. Formally, a
partition into bundles B<sub>1</sub>..B<sub>k</sub> with per-tile update probabilities
p<sub>i</sub> pays expected bytes
&Sigma;<sub>j</sub>&nbsp;[1&nbsp;&minus;&nbsp;&Pi;<sub>i&isin;B<sub>j</sub></sub>(1&nbsp;&minus;&nbsp;p<sub>i</sub>)]&nbsp;&middot;&nbsp;bytes(B<sub>j</sub>)
per deploy, which grows with bundle size and with churn. Chunking bounds it at 1/k of
the collection; grouping tiles by update cadence confines a change to the chunk that
carries it. The sharpest remedy is to serve updates as deltas against the cached
previous version (Compression Dictionary Transport). In a 392-photo
WebP bundle, a zstd delta against the prior bundle cost 25&nbsp;KB when 5 tiles changed
and 237&nbsp;KB when 50 changed, tracking the changed-files optimum and beating whole-atlas
re-download (2.8&nbsp;MB) by two orders of magnitude. The structural weakness thus
becomes proportional to churn rather than to bundle size.</p>
<p>A warm-cache simulation over a 200-tile WebP collection makes the full trade-off
explicit (Table&nbsp;4). Serving immutable individual files is the granularity ideal, a
returning client fetches only the changed tiles (12&nbsp;KB at 1% churn). A single
monolithic atlas is the opposite extreme: any change re-downloads the entire
1.47&nbsp;MB, 126x the individual cost at 1% churn. Chunking closes the gap
proportionally, 16 chunks cost 170&nbsp;KB at 1% churn against one atlas's 1.47&nbsp;MB,
but never reaches per-tile granularity. Dictionary-delta serving does: at 12&nbsp;KB for
1% churn it matches the individual-file optimum within one percent, and at 20% churn it
undercuts it (192 vs 218&nbsp;KB) because the shared dictionary compresses each new tile
against the old ones. The practical consequence is that an update-heavy collection can
keep the cold-load benefits of bundling and still get individual-file cache granularity,
by serving deltas rather than whole bundles.</p>
{warm_html}
{H3('A calibrated construction heuristic')}
<p>The cost above is not minimized by search; instead the measured curves calibrate a
greedy heuristic, implemented as a command-line tool (<code>atlas_optimizer</code>,
released with the study). The tool folds exact duplicates into shared coordinates;
partitions tiles by update cadence, lossless requirement, and dimensions; routes each
group to a pixel atlas (small lossy tiles), a byte-bundle (large or lossless tiles), or
individual files (tiny groups); and chunks each bundle. It emits the atlas and bundle
files, a CSS coordinate map, a loader snippet, and a per-group savings report. Validated against the study's own asset sets, it converts 521
icon-class tiles into four atlas chunks at 19% fewer bytes, and 521 photo thumbnails, of
which 21.6% are exact repeats, into four byte-bundle chunks at 21% fewer bytes, with 521
requests becoming four in both cases.</p>
{H3('Limitations')}
<p>Quality is measured by luma SSIM at a 0.97 target; a perceptual metric such as
SSIMULACRA2 or butteraugli would sharpen the matched-quality comparison. The
shared-palette result uses a synthetic limited-color corpus that is
the ideal case; anti-aliased production icons will realize less of it. The network study
emulates four profiles on a single-machine testbed rather than the open Internet, and
measures time-to-all-tiles-visible rather than a full field-metric suite. Decoded-memory
cost is bounded analytically and by the chunking recommendation but not yet profiled in
a live renderer. The HTTP/3 concurrency diagnosis rests on Resource Timing reconstruction; confirming the mechanism with qlog traces and testing its generality across servers and native Linux is future work. The byte results rest on one icon set and one photographic collection
plus purpose-built corpora, so the crossovers are calibrated rather than population
estimates; a wider survey across multiple icon libraries and photo sources, with
randomized N-subset sampling and bootstrap intervals, would turn the reported points
into distributions. The network numbers are medians of 7 cold loads per cell
without reported dispersion or significance tests, and the timing endpoint is
time-to-all-tiles-visible; user-centric metrics (first tile, above-the-fold completion,
LCP, decode CPU) and warm-cache multi-navigation behavior under realistic asset churn
are not measured and could change the recommended bundle size. Finally, AVIF and
JPEG&nbsp;XL are excluded by scope, though AVIF is now a material share of web imagery;
their larger container overhead and richer adaptivity would move the crossovers, and
AVIF is the first codec a follow-up should add.</p>

{H2('Conclusion')}
<p>Bundling small web images pays, and the study makes precise when and by how much for
the three formats that carry most of the web's images. Atlas small lossy tiles: icons
and thumbnails gain up to 30% under JPEG and up to 19% under WebP at matched
quality, and lossless flat art, the icon-set and map-marker case, gains 40&ndash;95%
with a strip-packed or shared-palette bundle that is smaller than even the best lossy
option. Serve larger photographs and lossless assets as a byte-bundle, which collapses
requests at zero byte cost, or, for photographic WebP, tune the encoder (noise shaping
plus adaptive deblocking) to turn the atlas penalty into a gain. Ship about four chunks
for loss resilience and bounded cache invalidation, deduplicate repeats explicitly, and
serve updates as dictionary deltas. On the wire, bundling is 4&ndash;9x faster to full
visibility on HTTP/1.1 and HTTP/3 and chiefly a byte optimization on HTTP/2. The unifying
account, that savings come from sharing fixed costs and losses from sharing adaptive
state, predicts every sign in the data and guides the accompanying construction
heuristic, which turns a directory of images into deployable bundles.</p>

<h2 class="refs-head">References</h2>
<div class="refs">
<p>[1] C. Johnson. Forgo JS packaging? Not so fast. Khan Academy Engineering, 2015.
https://blog.khanacademy.org/forgo-js-packaging-not-so-fast/</p>
<p>[2] C. Coyier. Musings on HTTP/2 and bundling. CSS-Tricks.
https://css-tricks.com/musings-on-http2-and-bundling/</p>
<p>[3] M. Varvello, K. Schomp, D. Naylor, J. Blackburn, A. Finamore, K. Papagiannaki.
Is the Web HTTP/2 Yet? Passive and Active Measurement (PAM), LNCS 9631, 2016.
doi:10.1007/978-3-319-30505-9_17</p>
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
<p>[10] D. Shea. CSS Sprites: Image Slicing's Kiss of Death. A List Apart, 2004.
https://alistapart.com/article/sprites/</p>
<p>[11] Google. Web Fundamentals: HTTP/2 and resource bundling guidance.
https://web.dev/articles/http2</p>
<p>[12] M. Belshe, R. Peon, M. Thomson. Hypertext Transfer Protocol Version 2 (HTTP/2).
RFC 7540, IETF, 2015.</p>
<p>[13] M. Bishop. HTTP/3. RFC 9114, IETF, 2022.</p>
<p>[14] J. Ruth, D. Kunze, O. Hohlfeld. Measuring HTTP/3: Adoption and Performance.
arXiv:2102.12358, 2021.</p>
<p>[15] U. Goel et al. Domain-Sharding for Faster HTTP/2 in Lossy Cellular Networks.
arXiv:1707.05836, 2017.</p>
<p>[16] Cloudinary. Image optimization documentation (format selection and the
&lt;5,000-pixel AVIF policy). https://cloudinary.com/documentation/image_optimization</p>
<p>[17] ITU-T T.81 / ISO&nbsp;IEC 10918-1. Digital compression and coding of
continuous-tone still images (JPEG), 1992.</p>
<p>[18] W3C. Portable Network Graphics (PNG) Specification, 3rd ed., 2003.
https://www.w3.org/TR/PNG/</p>
<p>[19] Google. WebP Container and Bitstream Specification.
https://developers.google.com/speed/webp/docs/riff_container</p>
<p>[20] J. Ratcliff. Texture atlas / sprite packing techniques. Game Developer, 2002.</p>
<p>[21] J. Jyl&auml;nki. A Thousand Ways to Pack the Bin: rectangle bin-packing
algorithms (skyline, MaxRects), 2010.</p>
<p>[22] J. Alakuijala, Z. Szabadka. Brotli Compressed Data Format. RFC 7932, IETF, 2016.</p>
<p>[23] Y. Collet, M. Kucherawy. Zstandard Compression and the application/zstd Media
Type. RFC 8878, IETF, 2021.</p>
<p>[24] P. Meenan, Y. Weiss. Compression Dictionary Transport. IETF draft / Chrome
Platform Status, 2024. https://datatracker.ietf.org/doc/draft-ietf-httpbis-compression-dictionary/</p>
<p>[25] Z. Wang, A. C. Bovik, H. R. Sheikh, E. P. Simoncelli. Image Quality Assessment:
From Error Visibility to Structural Similarity. IEEE Trans. Image Processing 13(4):600-612,
2004. doi:10.1109/TIP.2003.819861</p>
<p>[26] X. S. Wang, A. Balasubramanian, A. Krishnamurthy, D. Wetherall. Demystifying Page
Load Performance with WProf. USENIX NSDI, 2013.</p>
<p>[27] X. S. Wang, A. Balasubramanian, A. Krishnamurthy, D. Wetherall. How Speedy is
SPDY? USENIX NSDI, 2014.</p>
<p>[28] R. Netravali, A. Goyal, J. Mickens, H. Balakrishnan. Polaris: Faster Page Loads
Using Fine-grained Dependency Tracking. USENIX NSDI, 2016.</p>
<p>[29] R. Marx, T. Wijnants, P. Quax, A. Faes, W. Lamotte. Concatenation, Embedding and
Sharding: Do HTTP/1 Performance Best Practices Make Sense in HTTP/2? WEBIST, 2017.</p>
<p>[30] C. Sander, I. Kunze, K. Wehrle, J. Rüth. Sharding and HTTP/2 Connection Reuse
Revisited: Why Are There Still Redundant Connections? ACM IMC, 2021.
doi:10.1145/3487552.3487832</p>
<p>[31] N. Barman, M. G. Martini. An Evaluation of the Next-Generation Image Coding
Standard AVIF. IEEE QoMEX, 2020. doi:10.1109/QoMEX48832.2020.9123131</p>
<p>[32] B. Lévy, S. Petitjean, N. Ray, J. Maillot. Least Squares Conformal Maps for
Automatic Texture Atlas Generation. ACM SIGGRAPH / ACM TOG 21(3), 2002.
doi:10.1145/566654.566590</p>
</div>
<div class="footer">Alexander Apartsin &middot; 2026</div>
</body></html>"""

    out = ROOT / "docs" / "paper.html"
    out.write_text(html, encoding="utf-8")
    # the paper IS the site landing page
    (ROOT / "docs" / "index.html").write_text(html, encoding="utf-8")
    # content canaries
    for canary in ["Table 1.", "Table 2.", "Figure 1.", "Figure 2.", "Figure 3.",
                   "Figure 4.", "<svg",
                   "atlas_emoji_100.png", "Abstract", "References", "Table 4.",
                   "background-position", "object-view-box", "Cache-Control", "Table 3."]:
        assert canary in html, f"CANARY FAILED: {canary}"
    assert html.count("<svg") >= 4, "CANARY FAILED: expected 4 charts"
    assert html.count("aria-label") >= 4, "CANARY FAILED: chart accessibility labels"
    print(f"wrote {out} ({len(html):,} bytes), canaries pass")


if __name__ == "__main__":
    main()
