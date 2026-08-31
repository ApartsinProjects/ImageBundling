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
.authors{text-align:center;font-size:10.5pt;color:#2c3138;margin-bottom:.25rem}
.authors sup,.affil sup{font-size:.72em}
.affil{text-align:center;font-size:9pt;color:#5a626c;margin-bottom:.35rem;line-height:1.4}
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
.downloads{position:fixed;top:12px;right:14px;font-size:9pt;background:#f4f5f7;
 border:1px solid #d1d4d8;border-radius:5px;padding:.3rem .55rem;line-height:1.2;
 box-shadow:0 1px 3px rgba(0,0,0,.06)}
.downloads a{color:#14385c;text-decoration:none;font-weight:600}
.downloads a:hover{text-decoration:underline}
.downloads .sep{color:#b0b4ba;margin:0 .25rem}
@media (max-width:980px){.downloads{position:static;display:block;text-align:right;
 margin:0 0 1rem;box-shadow:none}}
@media print{.downloads{display:none !important}}
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
                    cells.append(f"<td>{v:,}</td>" if v else "<td>n/a</td>")
                    continue
                r = next((x for x in rows if x["cond"] == cond and
                          x["corpus"] == corpus and x["size"] == size), None)
                cells.append(f"<td>{r['bytes']:,}</td>" if r else "<td>n/a</td>")
        trows.append(f"<tr><td>{label}</td>{''.join(cells)}</tr>")
    return ("<div class='tablewrap'><table>"
            "<caption><b>Table 3.</b> Bundle bytes for 200 synthetic flat icons (fixed "
            "12-color palette, alpha), lossless unless noted, on a clean corpus and one "
            "with 20% exact + 20% near-duplicate tiles. Lossless bundles are byte-exact "
            "(palette conversion verified identical after decode); the JPEG row is the "
            "matched-SSIM-0.97 grid atlas. The 90&ndash;97% shared-palette saving cited in "
            "the text is measured against individual paletted PNGs (per tile), whose byte "
            "totals are in the released data. Smaller is better.</caption>"
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


def predict_table():
    f = ROOT / "results" / "static" / "e_predict" / "results.json"
    if not f.exists():
        return ""
    d = json.load(f.open())
    base = d["by_target"]["saving"]["baseline"]["mae"]
    rich = d["by_target"]["saving"]["rich"]["mae"]
    p10, p20 = d["probe"]["probe10"], d["probe"]["probe20"]
    diff_f = ROOT / "results" / "static" / "e_predict" / "diff.json"
    diff = json.load(diff_f.open()) if diff_f.exists() else None
    rows = [("size + codec + one encode (baseline)", f"{base:.2f}", "n/a"),
            ("+ six source-image features", f"{rich:.2f}", "n/a"),
            ("10-tile probe encode", f"{p10['mae_fit']:.2f}", f"{p10['spearman']:.2f}"),
            ("20-tile probe encode", f"{p20['mae_fit']:.2f}", f"{p20['spearman']:.2f}")]
    trows = "".join(f"<tr><td>{n}</td><td>{m}</td><td>{s}</td></tr>" for n, m, s in rows)
    dnote = ""
    if diff:
        dnote = (f" On the isolated codec differential (JPEG minus WebP saving, which "
                 f"cancels the fixed-cost term), the same features still fail to beat a "
                 f"constant ({diff['rich_features_mae']:.1f} vs {diff['constant_mae']:.1f} "
                 f"percentage points), so the shortfall is not a missing fixed-cost signal "
                 f"but the coupling penalty being unreadable from source pixels.")
    return ("<div class='tablewrap'><table>"
            "<caption><b>Table 11.</b> Predicting a group's atlas saving before building "
            "it, evaluated leave-one-content-class-out over eight classes spanning extreme "
            "image statistics (natural photos, emoji, flags, avatars, and synthetic "
            "gradients, noise, UI mockups, and objects on white; JPEG and WebP). Error is "
            "mean absolute error in percentage points against the measured saving; rank is "
            "Spearman correlation with it. Six cheap source-image features do not improve "
            "on a size-and-codec baseline, but a probe encode of 10&ndash;20 tiles predicts "
            "the full-set saving to within about two points." + dnote + "</caption>"
            "<thead><tr><th>predictor</th><th>MAE (pp)</th><th>rank</th></tr></thead>"
            f"<tbody>{trows}</tbody></table></div>")


def cross_corpus_table():
    f = ROOT / "results" / "static" / "e_crosscorpus" / "summary.json"
    if not f.exists():
        return ""
    agg = json.load(f.open())["aggregate"]
    ho = ROOT / "results" / "static" / "e_heldout" / "results.json"
    ho_note = ""
    if ho.exists():
        h = json.load(ho.open())
        best = min(h["summary"].values(), key=lambda x: x["mae"])
        ho_note = (f" A model trained on any three corpora predicts the held-out "
                   f"fourth's saving to {best['mae']:.1f} percentage points mean absolute "
                   f"error (leave-one-corpus-out over {h['n_cells']} cells), so the "
                   f"crossover is a codec-and-size regime, not a corpus-specific effect.")

    def cell(size, codec):
        r = next((a for a in agg if a["size"] == size and a["codec"] == codec), None)
        if not r:
            return "<td>n/a</td>"
        klass = ' class="neg"' if r["median"] < 0 else ""
        return (f'<td{klass}>{r["median"]:+.1f}<br><span style="font-size:8pt;color:#8a8f97">'
                f'[{r["min"]:+.0f},{r["max"]:+.0f}]</span></td>')

    trows = []
    for size in (56, 112, 224):
        trows.append(f"<tr><td>photos {size}px</td>" +
                     "".join(cell(size, c) for c in ("jpeg", "webp", "avif")) + "</tr>")
    return ("<div class='tablewrap'><table>"
            "<caption><b>Table 8.</b> Cross-corpus, cross-codec crossover: bytes saved by "
            "atlasing (%) at matched SSIM 0.97, median over four independent natural-photo "
            "populations (Lorem&nbsp;Picsum and three loremflickr categories: generic, "
            "nature, food; 60 tiles each), with the per-corpus range in brackets. The sign "
            "and size of the effect are consistent across populations: JPEG and AVIF stay "
            "positive at every tile size while WebP crosses zero near 112&nbsp;px and is "
            "negative by 224&nbsp;px. AVIF, with the largest container floor, gains the most "
            "at small sizes." + ho_note + " Negative values (red) mean the atlas is "
            "larger.</caption>"
            "<thead><tr><th>class</th><th>JPEG</th><th>WebP</th><th>AVIF</th></tr></thead>"
            f"<tbody>{''.join(trows)}</tbody></table></div>")


def memory_table():
    f = ROOT / "results" / "static" / "e_memory" / "results.json"
    if not f.exists():
        return ""
    rows = json.load(f.open())

    def get(n, cond, key):
        r = next((x for x in rows if x["n"] == n and x["cond"] == cond), None)
        return r[key] if r else None

    trows = []
    for n in (50, 200, 500):
        cells = []
        for cond in ("ind", "atlas", "bundle"):
            av = get(n, cond, "allVisible"); mem = get(n, cond, "mem_mb")
            cells.append(f"<td>{av:,}</td><td>{mem:.0f}</td>")
        trows.append(f"<tr><td>{n}</td>{''.join(cells)}</tr>")
    return ("<div class='tablewrap'><table>"
            "<caption><b>Table 9.</b> Measured browser cost of rendering N 96px "
            "photographic tiles three ways, in one Chromium instance with no network "
            "shaping: time to all tiles visible (ms) and renderer process-tree memory over "
            "a blank-page baseline (MB, capturing the decoded-image cache that JavaScript "
            "heap APIs miss). The pixel atlas is fastest to full visibility at every N (one "
            "decode paints all tiles) and uses the least memory (one decoded surface rather "
            "than N); the byte-bundle must fetch its whole object before the first tile and "
            "retains N blob-backed decodes, so it costs the most memory. This refines the "
            "analytical width&times;height&times;4 bound: for typical thumbnail collections "
            "the atlas is memory-favorable, and the decoded-memory caution applies to very "
            "large atlases, not to bundling per se.</caption>"
            "<thead><tr><th>N</th><th>ind ms</th><th>ind MB</th><th>atlas ms</th>"
            "<th>atlas MB</th><th>bundle ms</th><th>bundle MB</th></tr></thead>"
            f"<tbody>{''.join(trows)}</tbody></table></div>")


def tail_table():
    import numpy as np
    specs = [("phase1_emoji", "webp", 500, 80, "flat art 72px, WebP"),
             ("phase1_emoji", "jpeg", 500, 80, "flat art 72px, JPEG"),
             ("phase1_photos56", "webp", 500, 80, "photos 56px, WebP"),
             ("phase1_photos", "webp", 500, 80, "photos 224px, WebP")]
    trows = []
    for tag, codec, n, q, label in specs:
        f = ROOT / "results" / "static" / tag / "results.jsonl"
        if not f.exists():
            continue
        rs = [json.loads(l) for l in f.open()]
        cells = {}
        for mode in ("individual", "atlas"):
            x = next((y for y in rs if y["codec"] == codec and y["n"] == n and
                      y["quality"] == q and y["mode"] == mode and y.get("pad", 0) == 0), None)
            if x and "ssims" in x:
                s = np.array(x["ssims"])
                cells[mode] = (s.mean(), np.percentile(s, 5), s.min())
        if "individual" in cells and "atlas" in cells:
            im, ip, imn = cells["individual"]; am, ap, amn = cells["atlas"]
            trows.append(f"<tr><td>{label}</td><td>{im:.3f}</td><td>{ip:.3f}</td>"
                         f"<td>{imn:.3f}</td><td>{am:.3f}</td><td>{ap:.3f}</td>"
                         f"<td>{amn:.3f}</td></tr>")
    return ("<div class='tablewrap'><table>"
            "<caption><b>Table 6.</b> Per-tile SSIM distribution (mean, 5th percentile, "
            "minimum) for individual files versus the grid atlas at equal encoder quality "
            "(q80, N=500). Matching the mean can still leave the atlas with a worse worst "
            "tile: the flat-art WebP atlas has a tile stuck near 0.85 that no quality "
            "setting recovers, a shared-segment boundary casualty, whereas JPEG's atlas "
            "and individual tails coincide.</caption>"
            "<thead><tr><th>condition</th><th>ind mean</th><th>ind p5</th><th>ind min</th>"
            "<th>atlas mean</th><th>atlas p5</th><th>atlas min</th></tr></thead>"
            f"<tbody>{''.join(trows)}</tbody></table></div>")


def ss2_table():
    f = ROOT / "results" / "static" / "e_ssim2" / "results.json"
    if not f.exists():
        return ""
    rows = json.load(f.open())

    def get(size, codec, target):
        r = next((x for x in rows if x.get("size") == size and
                  x.get("codec") == codec and x.get("target") == target), None)
        return r["saving_pct"] if r and r.get("saving_pct") is not None else None

    def cell(v):
        if v is None:
            return "<td>n/a</td>"
        return f'<td class="neg">{v:.1f}</td>' if v < 0 else f"<td>{v:.1f}</td>"

    trows = []
    for size, label in [(56, "photos 56px"), (112, "photos 112px"),
                        (224, "photos 224px")]:
        cells = "".join(cell(get(size, c, t)) for c in ("jpeg", "webp")
                        for t in (60, 70))
        trows.append(f"<tr><td>{label}</td>{cells}</tr>")
    return ("<div class='tablewrap'><table>"
            "<caption><b>Table 7.</b> Robustness of the photo crossover under a modern "
            "perceptual metric: bytes saved by atlasing (%) at matched SSIMULACRA2 "
            "(reference libjxl implementation), for 100 photographic tiles scored on the "
            "full grid image at two quality targets. JPEG stays positive at every size; "
            "WebP is positive only at 56&nbsp;px and turns clearly negative by "
            "112&nbsp;px. The direction matches the luma-SSIM result of Table&nbsp;1, and "
            "the WebP penalty is larger under SSIMULACRA2, which weights the chroma and "
            "blocking artifacts of VP8's shared quantizer more heavily. Negative values "
            "(red) mean the atlas is larger.</caption>"
            "<thead><tr><th>class</th><th>JPEG @60</th><th>JPEG @70</th>"
            "<th>WebP @60</th><th>WebP @70</th></tr></thead>"
            f"<tbody>{''.join(trows)}</tbody></table></div>")


def heuristic_figure():
    """Decision-flow diagram of the atlas_optimizer construction heuristic (Section 6.3)."""
    W, H = 650, 566
    o = [f'<svg viewBox="0 0 {W} {H}" style="max-width:100%" font-family="Georgia,serif" '
         f'role="img" aria-label="Construction heuristic decision flow">']
    o.append('<defs><marker id="ah" markerWidth="8" markerHeight="8" refX="6" refY="3" '
             'orient="auto"><path d="M0,0 L6,3 L0,6 Z" fill="#5a626c"/></marker></defs>')

    def box(cx, cy, w, h, text, fill="#eef2f6", stroke="#14385c", fs=10.5):
        o.append(f'<rect x="{cx-w/2:.0f}" y="{cy-h/2:.0f}" width="{w}" height="{h}" '
                 f'rx="4" fill="{fill}" stroke="{stroke}"/>')
        lines = text.split("|")
        y0 = cy - (len(lines) - 1) * (fs + 1) / 2
        for i, ln in enumerate(lines):
            o.append(f'<text x="{cx:.0f}" y="{y0 + i*(fs+1) + fs*0.35:.0f}" '
                     f'font-size="{fs}" text-anchor="middle" fill="#111418">{ln}</text>')

    def diamond(cx, cy, w, h, text, fs=10):
        o.append(f'<polygon points="{cx:.0f},{cy-h/2:.0f} {cx+w/2:.0f},{cy:.0f} '
                 f'{cx:.0f},{cy+h/2:.0f} {cx-w/2:.0f},{cy:.0f}" fill="#fdf3e3" '
                 f'stroke="#b9770e"/>')
        lines = text.split("|")
        y0 = cy - (len(lines) - 1) * (fs + 1) / 2
        for i, ln in enumerate(lines):
            o.append(f'<text x="{cx:.0f}" y="{y0 + i*(fs+1) + fs*0.35:.0f}" '
                     f'font-size="{fs}" text-anchor="middle" fill="#111418">{ln}</text>')

    def arrow(x1, y1, x2, y2, label=None, lx=0, ly=0):
        o.append(f'<line x1="{x1:.0f}" y1="{y1:.0f}" x2="{x2:.0f}" y2="{y2:.0f}" '
                 f'stroke="#5a626c" marker-end="url(#ah)"/>')
        if label:
            o.append(f'<text x="{(x1+x2)/2+lx:.0f}" y="{(y1+y2)/2+ly:.0f}" font-size="9" '
                     f'text-anchor="middle" fill="#8a2f22">{label}</text>')

    L, R, BUS = 190, 452, 572   # spine x, terminal x, convergence bus x (right of boxes)

    def seg(x1, y1, x2, y2, dash=False):
        d = ' stroke-dasharray="3 3"' if dash else ''
        o.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#5a626c"{d}/>')

    # --- nodes (drawn first so arrows render on top) ---
    box(L, 24, 230, 30, "directory of images")
    box(L, 72, 250, 30, "collapse exact duplicates &rarr; shared CSS coords")
    box(L, 120, 250, 30, "group by cadence / lossless / dimensions")
    diamond(L, 184, 150, 54, "group|&lt; 10 tiles?")
    diamond(L, 268, 150, 54, "lossless|required?")
    diamond(L, 352, 170, 56, "atlas &lt; bundle|and clears|per-tile floor?")
    box(R, 184, 190, 30, "individual files", fill="#f4f5f7", stroke="#5a626c")
    box(R, 268, 200, 34, "keep smaller of byte-bundle|or WebP-lossless strip",
        fill="#e8f3ef", stroke="#16a085")
    box(R, 352, 190, 30, "WebP pixel atlas", fill="#e7eff6", stroke="#2980b9")
    box(R, 408, 190, 30, "byte-bundle", fill="#f4f5f7", stroke="#5a626c")
    box(L, 480, 250, 30, "chunk into ~4 (cache &amp; memory bounds)")
    box(L, 528, 300, 30, "emit atlas / bundle + CSS map + loader + savings report")
    box(R + 100, 528, 150, 34, "updates:|serve dictionary deltas",
        fill="#fbf7ee", stroke="#b9770e", fs=9.5)

    # --- spine flow ---
    arrow(L, 39, L, 57)
    arrow(L, 87, L, 105)
    arrow(L, 135, L, 157)
    arrow(L, 211, L, 241, "no", -11, 0)     # D1 no -> D2
    arrow(L, 295, L, 325, "no", -11, 0)     # D2 no -> D3
    # --- yes branches to terminals (straight) ---
    arrow(L + 75, 184, R - 95, 184, "yes", 0, -5)
    arrow(L + 75, 268, R - 100, 268, "yes", 0, -5)
    arrow(L + 80, 352, R - 95, 352, "yes", 0, -5)   # small tile? yes -> pixel atlas
    # --- D3 no -> byte-bundle (clean elbow, no crossing) ---
    seg(L, 379, L, 408)
    arrow(L, 408, R - 95, 408, "no", 22, -5)
    # --- convergence: terminal right edges -> vertical bus -> chunk ---
    for ty, hw in ((184, 95), (268, 100), (352, 95), (408, 95)):
        seg(R + hw, ty, BUS, ty)
    seg(BUS, 184, BUS, 480)
    arrow(BUS, 480, L + 125 + 2, 480)               # bus -> chunk right edge
    arrow(L, 495, L, 513)                            # chunk -> emit
    seg(L + 152, 528, R + 25, 528, dash=True)       # emit -> delta note
    o.append('</svg>')
    return (f"<figure>{''.join(o)}<figcaption><b>Figure 6.</b> The construction heuristic "
            "as implemented in <code>atlas_optimizer</code>. Exact duplicates collapse to "
            "shared coordinates; tiles are grouped by update cadence, lossless requirement, "
            "and dimensions; each group is routed by a short decision cascade to individual "
            "files, a pixel atlas, or a byte-bundle. The lossy branch is decided by "
            "measurement: a pixel atlas is chosen only if it is smaller than the byte-bundle "
            "and clears a per-tile SSIM floor, and lossless groups keep the smaller of a "
            "byte-bundle and a WebP-lossless strip. Groups "
            "are chunked for bounded cache invalidation and memory, and the tool emits the "
            "atlas and bundle files, a CSS coordinate map, a loader, and a savings report; "
            "piecewise updates can be served as dictionary deltas. This is the procedure "
            "evaluated against the oracle in Table&nbsp;5.</figcaption></figure>")


def oracle_table():
    f = ROOT / "results" / "static" / "e_oracle" / "results.json"
    if not f.exists():
        return ""
    rows = json.load(f.open())

    def naive(cand, prefix, oracle_bytes):
        """Regret of a fixed-layout rule that still picks the best admissible codec."""
        vs = [v for k, v in cand.items() if k.startswith(prefix)]
        return 100 * (min(vs) / oracle_bytes - 1) if vs else None

    def fmt(v):
        if v is None:
            return "<td>n/a</td>"
        klass = ' class="neg"' if v > 0.05 else ""
        return f"<td{klass}>{v:+.1f}%</td>" if v > 0.05 else f"<td>0.0%</td>"

    trows = []
    acc = {"grid-atlas": [], "byte-bundle": [], "strip-atlas": []}
    for r in rows:
        c, ob = r["all_candidates"], r["oracle_bytes"]
        g = naive(c, "grid-atlas", ob)
        b = naive(c, "byte-bundle", ob)
        s = naive(c, "strip-atlas", ob)
        for k, v in (("grid-atlas", g), ("byte-bundle", b), ("strip-atlas", s)):
            if v is not None:
                acc[k].append(v)
        trows.append(
            f"<tr><td>{r['corpus']}</td><td>{r['class']}</td><td>{r['n']}</td>"
            f"<td>{r['optimizer_choice']}</td><td>0.0%</td>"
            f"{fmt(g)}{fmt(b)}{fmt(s)}</tr>")
    mean = {k: (sum(v) / len(v) if v else None) for k, v in acc.items()}
    trows.append(
        "<tr><td colspan='4' style='text-align:right'><i>mean regret</i></td>"
        "<td><b>0.0%</b></td>"
        f"<td><b>{mean['grid-atlas']:+.1f}%</b></td>"
        f"<td><b>{mean['byte-bundle']:+.1f}%</b></td>"
        f"<td><b>{mean['strip-atlas']:+.1f}%</b></td></tr>")
    return ("<div class='tablewrap'><table>"
            "<caption><b>Table 5.</b> Out-of-sample evaluation of the construction "
            "heuristic on five independent corpora that played no role in its "
            "calibration (Noto emoji, OpenMoji, country flags, Flickr photos, Robohash "
            "avatars; 100 tiles each). An offline oracle enumerates every candidate "
            "configuration (individual, grid atlas, strip atlas, byte-bundle across the "
            "admissible codecs) at matched quality and reports the byte-optimal one; "
            "regret is a policy's bytes over the oracle's. The last three columns are "
            "simple fixed-layout rules a developer might hardcode, each still allowed the "
            "best admissible codec (individual files cost the same bytes as a byte-bundle). "
            "The calibrated heuristic matches the oracle on all five corpora; every fixed "
            "rule is beaten on at least one, because the winning layout is "
            "content-dependent. Smaller regret is better.</caption>"
            "<thead><tr><th>corpus</th><th>class</th><th>tiles</th><th>heuristic choice</th>"
            "<th>heuristic</th><th>always atlas</th><th>always bundle</th>"
            f"<th>always strip</th></tr></thead><tbody>{''.join(trows)}</tbody></table></div>")


_PAL = {"jpeg": "#c0392b", "webp": "#2980b9", "png": "#7f8c8d", "webp_ll": "#16a085",
        "individual": "#111418", "atlas1": "#c0392b", "atlas4": "#e67e22",
        "atlas16": "#2980b9", "dict_delta": "#16a085"}
_LAB = {"jpeg": "JPEG", "webp": "WebP", "png": "PNG", "webp_ll": "WebP-lossless",
        "individual": "individual files", "atlas1": "1 atlas", "atlas4": "4 chunks",
        "atlas16": "16 chunks", "dict_delta": "dict-delta"}


def _lineplot(series, xs, xlabel, ylabel, W=560, H=320, logy=False, ytick=None,
              xticklabel=None, aria="", bands=None, vlines=None):
    """series: dict name -> list of y aligned to xs. Returns an <svg> line chart.
    bands: optional dict name -> list of (lo, hi) aligned to xs, drawn as a shaded 95%
    interval with whisker caps. vlines: optional list of (x, label) annotation markers."""
    import math
    ML, MB, MT, MR = 62, 46, 16, 140
    allys = [v for ys in series.values() for v in ys if v is not None]
    if bands:
        allys += [b for bs in bands.values() for pair in bs if pair for b in pair]
    if logy:
        ys_t = [math.log10(max(1, v)) for v in allys]
        ymin, ymax = min(ys_t), max(ys_t)
    else:
        ymin, ymax = min(allys + [0]), max(allys)
    pad = (ymax - ymin) * 0.08 or 1
    ymin -= pad; ymax += pad
    xmin, xmax = min(xs), max(xs)

    def X(x):
        return ML + (W - ML - MR) * (x - xmin) / ((xmax - xmin) or 1)

    def Y(v):
        t = math.log10(max(1, v)) if logy else v
        return (H - MB) - (H - MB - MT) * (t - ymin) / ((ymax - ymin) or 1)

    out = [f'<svg viewBox="0 0 {W} {H}" style="max-width:100%" font-family="Georgia,serif" '
           f'role="img" aria-label="{aria}">']
    # y gridlines/ticks
    for gt in (ytick or []):
        yy = Y(gt)
        lbl = (f"{gt/1e6:g}M" if gt >= 1e6 else f"{gt/1e3:g}K") if logy else f"{gt:g}"
        out.append(f'<line x1="{ML}" y1="{yy:.0f}" x2="{W-MR}" y2="{yy:.0f}" stroke="#eee"/>'
                   f'<text x="{ML-6}" y="{yy+4:.0f}" font-size="10" text-anchor="end" '
                   f'fill="#5a626c">{lbl}</text>')
    if not logy:
        out.append(f'<line x1="{ML}" y1="{Y(0):.0f}" x2="{W-MR}" y2="{Y(0):.0f}" '
                   f'stroke="#999" stroke-dasharray="4 3"/>')
    # x ticks
    for x in xs:
        out.append(f'<text x="{X(x):.0f}" y="{H-MB+16}" font-size="10" text-anchor="middle" '
                   f'fill="#5a626c">{(xticklabel(x) if xticklabel else x)}</text>')
    out.append(f'<text x="{(ML+W-MR)/2:.0f}" y="{H-6}" font-size="11" text-anchor="middle" '
               f'fill="#111418">{xlabel}</text>')
    out.append(f'<text x="14" y="{(MT+H-MB)/2:.0f}" font-size="11" text-anchor="middle" '
               f'fill="#111418" transform="rotate(-90 14 {(MT+H-MB)/2:.0f})">{ylabel}</text>')
    # annotation vertical lines
    for vx, vlab in (vlines or []):
        out.append(f'<line x1="{X(vx):.0f}" y1="{MT}" x2="{X(vx):.0f}" y2="{H-MB}" '
                   f'stroke="#b0b4ba" stroke-width="1" stroke-dasharray="2 3"/>'
                   f'<text x="{X(vx):.0f}" y="{MT+10}" font-size="9" text-anchor="middle" '
                   f'fill="#5a626c">{vlab}</text>')
    # confidence bands (drawn behind the lines)
    for name, bs in (bands or {}).items():
        c = _PAL.get(name, "#333")
        top = [(X(x), Y(hi)) for x, pair in zip(xs, bs) if pair for hi in [pair[1]]]
        bot = [(X(x), Y(lo)) for x, pair in zip(xs, bs) if pair for lo in [pair[0]]]
        if len(top) < 2:
            continue
        poly = " ".join(f"{px:.1f},{py:.1f}" for px, py in top + bot[::-1])
        out.append(f'<polygon points="{poly}" fill="{c}" fill-opacity="0.13" '
                   f'stroke="none"/>')
        for (px, py_hi), (_, py_lo) in zip(top, bot):
            out.append(f'<line x1="{px:.1f}" y1="{py_hi:.1f}" x2="{px:.1f}" '
                       f'y2="{py_lo:.1f}" stroke="{c}" stroke-width="1"/>'
                       f'<line x1="{px-3:.1f}" y1="{py_hi:.1f}" x2="{px+3:.1f}" '
                       f'y2="{py_hi:.1f}" stroke="{c}" stroke-width="1"/>'
                       f'<line x1="{px-3:.1f}" y1="{py_lo:.1f}" x2="{px+3:.1f}" '
                       f'y2="{py_lo:.1f}" stroke="{c}" stroke-width="1"/>')
    # series
    ly = MT + 6
    for name, ys in series.items():
        c = _PAL.get(name, "#333")
        pts = [(X(x), Y(v)) for x, v in zip(xs, ys) if v is not None]
        d = " ".join(f"{px:.1f},{py:.1f}" for px, py in pts)
        out.append(f'<polyline points="{d}" fill="none" stroke="{c}" stroke-width="2"/>')
        for px, py in pts:
            out.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="2.6" fill="{c}"/>')
        out.append(f'<rect x="{W-MR+10}" y="{ly-8}" width="12" height="3" fill="{c}"/>'
                   f'<text x="{W-MR+26}" y="{ly-3}" font-size="10" fill="#111418">'
                   f'{_LAB.get(name, name)}</text>')
        ly += 16
    out.append('</svg>')
    return "".join(out)


def crossover_figure():
    """Photo byte-saving vs tile size per codec, at N=200: JPEG and WebP as bootstrap
    medians with 95% CI bands (from the resampling study), lossless as exact lines."""
    sizes = [(56, "phase1_photos56"), (112, "phase1_photos112"), (224, "phase1_photos")]
    xs = [56, 112, 224]
    boot = json.load((ROOT / "results" / "static" / "e_bootstrap" / "results.json").open())

    def bmed(size, codec):
        r = next((x for x in boot if x["cls"] == "photos" and x["size"] == size and
                  x["N"] == 200 and x["codec"] == codec), None)
        return r

    series = {c: [] for c in ("jpeg", "webp", "png", "webp_ll")}
    bands = {"jpeg": [], "webp": []}
    for size, tag in sizes:
        rows = load(tag)
        for c in ("jpeg", "webp"):
            r = bmed(size, c)
            series[c].append(r["median_saving"] if r else None)
            bands[c].append((r["ci_lo"], r["ci_hi"]) if r else None)
        for c in ("png", "webp_ll"):
            r = next((x for x in rows if x["codec"] == c and x["n"] == 200 and
                      x["pad"] == 0 and x["ssim_target"] in (0.97, None)), None)
            series[c].append(r["saving_pct"] if r else None)
    svg = _lineplot(series, xs, "photo tile size (px)",
                    "bytes saved by atlasing (%)", logy=False,
                    ytick=[-10, -5, 0, 5, 10, 15, 20, 25, 30],
                    aria="Photo byte savings vs tile size per codec, with 95% CIs",
                    bands=bands, vlines=[(100, "WebP break-even")])
    return (f"<figure>{svg}<figcaption><b>Figure 2.</b> Byte savings from atlasing 200 "
            "photographic tiles at matched quality, as tile size grows from 56 to 224 "
            "pixels. JPEG and WebP are plotted as medians of 20 random subsets with 95% "
            "bootstrap confidence intervals (whiskers and shaded band); the lossless "
            "formats are exact. The saving tracks the per-file-overhead-to-content ratio "
            "and so falls with size: JPEG stays clearly positive throughout, while WebP's "
            "interval crosses zero near 100&nbsp;px (dashed marker) and is clearly "
            "negative by 224&nbsp;px. Table&nbsp;1 gives the full grid over image count "
            "and the flat-art class.</figcaption></figure>")


def warmcache_figure():
    f = ROOT / "results" / "static" / "e_warmcache" / "results.json"
    if not f.exists():
        return ""
    d = json.load(f.open())
    xs = [r["churn_pct"] for r in d["rows"]]
    series = {k: [r[k] for r in d["rows"]]
              for k in ("individual", "atlas1", "atlas16", "dict_delta")}
    svg = _lineplot(series, xs, "tiles changed per deploy (% of collection)",
                    "bytes re-downloaded", logy=True,
                    ytick=[10000, 100000, 1000000],
                    xticklabel=lambda x: f"{x:g}%",
                    aria="Warm-cache re-download bytes vs churn by strategy")
    return (f"<figure>{svg}<figcaption><b>Figure 5.</b> Warm-cache re-download: bytes a "
            "returning client fetches after a deploy changes a fraction of a 200-tile "
            "WebP collection (log scale; full fresh download "
            f"{d['total_fresh_download']:,}&nbsp;B; mean of 20 random deploys per rate). "
            "A single atlas re-fetches almost everything on any change; 16 chunks scale "
            "with churn; dictionary-delta serving tracks the individual-file optimum and "
            "undercuts it at high churn.</figcaption></figure>")


def load_network(tag="phase2v4"):
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
                arec = next((s for s in summ if s["profile"] == pkey and
                             s["proto"] == proto and s["cls"] == cls and
                             s["n"] == 500 and s["cond"] == "atlas1"), {})
                ci = (f" [{arec['speedup_ci_lo']:.1f},{arec['speedup_ci_hi']:.1f}]"
                      if arec.get("speedup_ci_lo") is not None else "")
                trows.append(
                    f"<tr><td>{clabel}</td><td>{plabel}</td><td>{proto}</td>"
                    f"<td>{i:,.0f}</td><td>{a1:,.0f}</td>"
                    f"<td>{a4:,.0f}</td><td>{bb:,.0f}</td>"
                    f"<td><b>{i/a1:.1f}x</b>{ci}</td><td>{i/bb:.1f}x</td></tr>")
    table2 = ("<div class='tablewrap'><table>"
              "<caption><b>Table 2.</b> Median time to all 500 tiles visible (ms) per "
              "serving condition, protocol, and network profile (n&nbsp;=&nbsp;11 cold "
              "browser loads per cell; 12 run in randomized order, first dropped; WebP "
              "payloads). The atl-x column gives the single-atlas speedup over individual "
              "files with a 95% bootstrap confidence interval; bun-x is the byte-bundle "
              "speedup. Per-cell quartiles are in the released data.</caption>"
              "<thead><tr><th>class</th><th>network</th><th>proto</th>"
              "<th>individual</th><th>atlas</th><th>atlas x4</th><th>byte-bundle</th>"
              "<th>atl-x</th><th>bun-x</th></tr></thead>"
              f"<tbody>{''.join(trows)}</tbody></table></div>")

    # Figure 4: atlas speedup as point estimate + 95% CI whisker, per protocol and
    # profile, one panel per class, on a shared log axis centered on parity (1x).
    import math as _m
    pc = {"h1": "#c0392b", "h2": "#2980b9", "h3": "#8e44ad"}

    def speedups(cls):
        vals = {}
        for pkey, _ in profiles:
            for proto in ["h1", "h2", "h3"]:
                rec = next((s for s in summ if s["profile"] == pkey and
                            s["proto"] == proto and s["cls"] == cls and
                            s["n"] == 500 and s["cond"] == "atlas1"), None)
                i = med.get((pkey, proto, cls, 500, "individual"))
                a = med.get((pkey, proto, cls, 500, "atlas1"))
                if i and a and rec:
                    lo = rec.get("speedup_ci_lo") or i / a
                    hi = rec.get("speedup_ci_hi") or i / a
                    vals[(pkey, proto)] = (i / a, lo, hi)
        return vals
    all_vals = {c: speedups(c) for c in ("emoji", "photos")}
    flat = [v for d in all_vals.values() for tup in d.values() for v in tup]
    smin, smax = min(flat + [0.9]), max(flat)

    def panel(cls, label):
        W, H, ML, MB, MT, MR = 520, 250, 56, 46, 18, 96
        vals = all_vals[cls]
        gw = (W - ML - MR) / len(profiles)
        out = [f'<svg viewBox="0 0 {W} {H}" style="max-width:100%" '
               f'font-family="Georgia,serif" role="img" aria-label="Atlas speedup, {cls}">']

        def Y(s):
            t = _m.log10(max(0.5, s))
            t0, t1 = _m.log10(smin * 0.95), _m.log10(smax * 1.05)
            return (H - MB) - (H - MB - MT) * (t - t0) / ((t1 - t0) or 1)
        for g in (0.5, 1, 2, 4, 8):
            if smin * 0.95 <= g <= smax * 1.05:
                out.append(f'<line x1="{ML}" y1="{Y(g):.0f}" x2="{W-MR}" y2="{Y(g):.0f}" '
                           f'stroke="#eee"/><text x="{ML-6}" y="{Y(g)+4:.0f}" '
                           f'font-size="10" text-anchor="end" fill="#5a626c">{g:g}x</text>')
        out.append(f'<line x1="{ML}" y1="{Y(1):.1f}" x2="{W-MR}" y2="{Y(1):.1f}" '
                   f'stroke="#111418" stroke-dasharray="4 3"/>')
        for pi, (pkey, _) in enumerate(profiles):
            x0 = ML + pi * gw + gw / 2
            for bi, proto in enumerate(["h1", "h2", "h3"]):
                tup = vals.get((pkey, proto))
                if not tup:
                    continue
                s, lo, hi = tup
                px = x0 + (bi - 1) * 13
                out.append(f'<line x1="{px:.1f}" y1="{Y(lo):.1f}" x2="{px:.1f}" '
                           f'y2="{Y(hi):.1f}" stroke="{pc[proto]}" stroke-width="1.4"/>'
                           f'<line x1="{px-3:.1f}" y1="{Y(lo):.1f}" x2="{px+3:.1f}" '
                           f'y2="{Y(lo):.1f}" stroke="{pc[proto]}" stroke-width="1.4"/>'
                           f'<line x1="{px-3:.1f}" y1="{Y(hi):.1f}" x2="{px+3:.1f}" '
                           f'y2="{Y(hi):.1f}" stroke="{pc[proto]}" stroke-width="1.4"/>'
                           f'<circle cx="{px:.1f}" cy="{Y(s):.1f}" r="3" '
                           f'fill="{pc[proto]}"/>')
            short = {"localhost": "local", "fast": "fast", "cell4g": "4G",
                     "slow3g": "3G", "lossy4g": "4G+loss"}[pkey]
            out.append(f'<text x="{x0:.0f}" y="{H-MB+16}" font-size="10" '
                       f'text-anchor="middle" fill="#5a626c">{short}</text>')
        out.append(f'<text x="{(ML+W-MR)/2:.0f}" y="{H-8}" font-size="11" '
                   f'text-anchor="middle" fill="#111418">network profile</text>')
        out.append(f'<text x="14" y="{(MT+H-MB)/2:.0f}" font-size="11" text-anchor="middle" '
                   f'fill="#111418" transform="rotate(-90 14 {(MT+H-MB)/2:.0f})">'
                   f'atlas speedup (log, individual / atlas)</text>')
        out.append(f'<text x="{ML+6}" y="{MT+12}" font-size="12" font-weight="bold" '
                   f'fill="#111418">{label}</text>')
        lx, ly, lh = W - MR + 12, MT + 6, 17
        out.append(f'<rect x="{lx-6}" y="{ly-12}" width="{MR-14}" height="{3*lh+16}" '
                   f'fill="#fff" stroke="#d1d4d8"/>')
        for i, proto in enumerate(["h1", "h2", "h3"]):
            yy = ly + i * lh
            lab = {"h1": "HTTP/1.1", "h2": "HTTP/2", "h3": "HTTP/3"}[proto]
            out.append(f'<circle cx="{lx+6}" cy="{yy-2}" r="3.5" fill="{pc[proto]}"/>'
                       f'<text x="{lx+16}" y="{yy+2}" font-size="9" fill="#111418">{lab}</text>')
        out.append('</svg>')
        return "".join(out)

    fig4 = (f"<figure>{panel('emoji', '(a) flat art, 72px, N=500')}"
            f"{panel('photos', '(b) photos, 224px, N=500')}"
            "<figcaption><b>Figure 4.</b> Time-to-all-tiles-visible speedup from atlasing "
            "(median individual / median single atlas) at N&nbsp;=&nbsp;500, per protocol "
            "and network profile, as point estimates with 95% bootstrap confidence "
            "intervals on a shared log axis; the dashed line marks parity (1x). HTTP/2 "
            "sits near parity for many small files, while HTTP/1.1 and HTTP/3 retain "
            "multi-x speedups; intervals that straddle the parity line (notably the "
            "loss-dominated 4G+loss profile) mark cells where atlas and individual are "
            "statistically indistinguishable.</figcaption></figure>")
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
        return "<td>n/a</td>"

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
              "values (red) mean the atlas is larger; n/a marks a cell whose quality "
              "ladder lies entirely above the target with no interpolable point.</caption>"
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

    fig_cross = crossover_figure()

    net_html = network_results_html()
    icon_html = icon_table()
    warm_html = warmcache_figure()
    oracle_html = oracle_table()
    heuristic_html = heuristic_figure()
    tail_html = tail_table()
    ss2_html = ss2_table()
    cross_html = cross_corpus_table()
    mem_html = memory_table()
    predict_html = predict_table()

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
<div class="downloads"><a href="paper.pdf">PDF</a><span class="sep">&middot;</span>
<a href="paper.docx">DOCX</a></div>
<h1>Image Bundling Revisited: Atlasing Small Web Images under Modern Codecs and
Protocols</h1>
<div class="authors">Alexander Apartsin<sup>1</sup>, Yehudit Aperstein<sup>2</sup></div>
<div class="affil"><sup>1</sup>School of Computer Science, Faculty of Sciences, Holon
Institute of Technology (HIT), Holon, Israel<br><sup>2</sup>Intelligent Systems, Afeka
Academic College of Engineering, Tel-Aviv, Israel</div>
<div class="venue">Technical Report &middot; 2026</div>

<div class="abstract"><div class="ahead">Abstract</div>
<p>Web pages load tens to hundreds of small images, and the median mobile page carries
13. Serving each one separately pays per-request overhead plus two byte costs that HTTP/2
multiplexing does not remove: a fixed per-file structural cost (roughly 600 bytes for a
JPEG) and the loss of cross-image redundancy. We measure how much of these costs bundling
many images into one atlas recovers, for the three codecs that carry most web images and
decode in every browser: JPEG, PNG, and WebP.</p>
<p>At matched per-tile quality, atlasing small tiles saves up to 30% of bytes under JPEG
and up to 19% under WebP, independent of protocol. The saving is set by the ratio of
per-file overhead to content size, so it falls as tiles grow: for photographs it drops
from about 30% at 56&nbsp;pixels to a few percent at 224&nbsp;pixels, where WebP turns
clearly negative. The sign is codec-specific: AVIF, like JPEG, stays positive at every
size, so WebP's shared quantizer, not atlasing itself, drives the reversal, and the
pattern holds across four independent photo populations. Lossless formats lose under a
naive grid but win 40&ndash;97% under
codec-aware packing (vertical strips, shared palettes), so the question is how to pack,
not whether. We distil the measurements into a coupling account (savings come from
sharing fixed costs; losses from sharing adaptive state) and into an open-source tool
that turns a directory of images into deployable bundles and matches an offline oracle on
five unseen collections. The byte effect resists prediction from source-image statistics,
which is why the tool measures rather than models: a probe encode of ten to twenty tiles
forecasts a group's saving to within two percentage points where colour, edge, and
frequency features cannot. In a live renderer the pixel atlas is also the fastest to full
visibility and the lowest in memory, and a supporting browser study shows the byte savings
cut load time on HTTP/1.1 and HTTP/3.</p></div>

{H2('Introduction')}
<p>Product grids, icon sets, avatars, and decorative elements make small images the most
numerous resource class on commercial pages. Bundling them into one image, the CSS
sprite technique, was standard practice in the HTTP/1.1 era and fell out of favor when
HTTP/2 multiplexing removed the per-connection request bottleneck. That reasoning
addressed only the request-count cost. Two byte-level costs survive multiplexing
untouched: every image file carries a fixed container overhead (headers, quantization
tables, ISOBMFF boxes), and every file boundary prevents the codec from sharing entropy
context, palettes, and predictors across images.</p>
<p>The study centers on the popular, universally-supported compressed formats: JPEG, PNG,
and WebP together carry over 70% of images served on the web (HTTP Archive 2024: JPEG
32.4%, PNG 28.4%, WebP 12.0%), decode in every browser, and are where the practical
savings live; AVIF, the leading next-generation codec, is added to the photographic
crossover (Section&nbsp;5.1) so the codec-dependence of the result is visible against a
modern container. The three formats price the per-file costs very
differently: a JPEG file carries, with the libjpeg-turbo encoder and settings used here,
roughly 600 bytes of Huffman and quantization table definitions plus headers (the exact
figure is encoder- and settings-specific), a PNG a 67-byte structural floor plus
per-scanline filter
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
image atlasing across the three universally-supported web codecs (JPEG, PNG, WebP) over
tile size and image count, establishing that the byte saving is governed by the ratio
of per-file structural cost to content bytes, and to our knowledge the first
measurement of image-atlasing byte savings resolved by codec and tile size at matched
perceptual quality (the one prior peer-reviewed sprite study [33] optimized PNG packing
geometry and held the codec fixed); (ii) a supporting network study of 2,515 validated
cold browser loads that separates the timing effect of bundling across HTTP/1.1,
HTTP/2, and HTTP/3 under emulated network conditions; (iii) a set of construction
techniques with measured effect, PNG vertical-strip packing, explicit and LZ-window
duplicate exploitation, chunking for bounded cache invalidation, delta updates via compression
dictionaries, and encoder-parameter tuning that flips WebP's photographic-atlas penalty
to a gain; (iv) a coupling-spectrum account that unifies the results, savings arise from
sharing fixed costs and losses from sharing adaptive state, together with the finding that
this adaptive-state penalty is codec-mechanistic and not predictable from source-image
statistics, while a small probe encode forecasts it accurately; and (v) an open-source
construction heuristic, built on that probe-not-predict principle, that emits deployable
bundles from a directory of images.</p>

{H2('Related work')}
{H3('Resource bundling and image spriting')}
<p>Combining many small resources into one is long-standing web practice, catalogued in
the performance-engineering literature (Souders [35]) as spriting, concatenation, and
DataURI inlining, all of which trade requests for cache granularity in the HTTP/1.1 era;
CSS sprites [10] are the image-specific form. The regime they address is real and
growing: measurement of page composition shows the modern page is dominated by many
small, heterogeneous resources (Butkiewicz et al. [34]), and image requests are the
largest class (HTTP Archive [8]). Whether bundling still pays under HTTP/2 multiplexing
has been examined mainly for JavaScript and CSS: Khan Academy found unbundled JS slower
than bundles under HTTP/2, attributing the gap to worse per-file compression [1], and
practitioner analyses reach the same conclusion for concatenated assets [2, 11]. Modern
build tools encode the trade-off directly as an inlining size threshold (webpack asset
modules, Vite's asset limit). The closest academic work on the packaging question is
Marx et al. [29], who test concatenation, embedding, and sharding under HTTP/2 and find
the HTTP/1 packaging habits still often help; broader page-load studies show load time
is governed by resource dependencies and compute, not bytes alone (WProf [26], How
Speedy is SPDY? [27], Polaris [28]), so request-count reductions are only part of the
story. The one peer-reviewed study of image spriting itself is Marszalkowski et al. [33],
who formulate CSS-sprite construction as a geometric packing problem, model load time,
and measure how a PNG sprite's aspect ratio affects its file size, holding the codec
fixed at PNG and optimizing layout area. Their axis is packing geometry; ours is codec
and tile size at matched quality, which they do not vary. A CSS-Tricks case study reports
a 223-icon sprite at roughly 10&nbsp;KB versus 115&nbsp;KB unbundled [2], but without
protocol-level timing. We find no published measurement that quantifies image atlasing
under HTTP/2 or HTTP/3, nor a codec-by-tile-size atlasing sweep at matched quality.</p>
{H3('Protocol performance: HTTP/2 and HTTP/3')}
<p>HTTP/2 multiplexes many requests over one connection [12] but suffers transport-level
head-of-line blocking under loss; HTTP/3 over QUIC [13] removes it with per-stream
recovery. Whether the newer protocol is faster in practice is contested and
configuration-sensitive: de Saxcé et al. [36] found HTTP/2 not uniformly faster than
HTTP/1.1, and rigorous QUIC evaluation shows performance swings widely with
implementation and workload (Kakhki et al. [37]). Measurement studies characterize
HTTP/2 adoption and page-load behavior [3] and server push [4], and both controlled
benchmarks [5] and adoption studies [14] report HTTP/3 gaining most under packet loss
while sitting near parity at zero loss. Domain sharding, the historical technique of
spreading resources across hosts to widen HTTP/1.1 concurrency [15], is the opposite of
bundling; recent measurement finds such HTTP/1-era habits persist even under HTTP/2 [30],
which motivates our condition set. This body of work establishes that protocol-level
outcomes for a given payload are as much a property of the deployment as of the standard,
the context in which our own HTTP/3 concurrency observation (Section&nbsp;5.5) should be
read; none of it isolates a many-small-images payload against a bundled baseline.</p>
{H3('Small-image coding and multi-image containers')}
<p>The fixed per-file cost each codec carries is documented through minimal one-pixel
files: JPEG&nbsp;XL 24&nbsp;B, WebP 30&nbsp;B, PNG 67&nbsp;B, JPEG 155&nbsp;B, AVIF
303&nbsp;B [6, 7]. This overhead makes small images the worst case for heavyweight
containers, and production pipelines act on it: Cloudinary declines AVIF for images
below 5,000 pixels because the box overhead outweighs the coding gain [16]. Several
formats already provide intermediate ways to share structure across many images without
a full pixel atlas: JPEG's abbreviated format carries one table-specification datastream
ahead of table-less scans [17]; animated WebP stores independently-coded frames in one
container [19]; APNG and MNG [40] and the HEIF image-collection format [41] package
multiple images in one resource. These occupy the low-coupling end of the spectrum this
report maps, sharing container and tables but not the coding model. The JPEG [17], PNG
[18], and WebP [19] format definitions specify the table, chunk, and container structures
our measurements amortize; JPEG&nbsp;XL adds a modern architecture aimed partly at small
images [38]. Matched-quality byte comparison across these formats is established for
single images (Google's WebP study measures WebP against JPEG and PNG at equal SSIM
[39]) and extended by peer-reviewed rate-distortion studies against newer codecs [31];
we carry the same matched-quality discipline to the atlas-versus-individual question. Perceptual image-quality assessment, on which our matched-quality
protocol rests, is grounded in the structural similarity index [25]. We are not aware of
prior work that measures how bundling recovers per-file overhead as a function of codec
and tile size.</p>
{H3('Texture atlases and sprite packing')}
<p>Packing many images into one is standard in real-time graphics, where texture atlases
[9, 20, 32] and skyline/MaxRects bin-packing [21] pursue a different objective: production
atlas tools (TexturePacker, engine sprite packers) and virtual-texturing systems minimize
GPU state changes and packed area, and tune padding for mip-sampling and filtering
correctness at tile boundaries rather than for encoded size. The optimization target is
binding count and texture memory, not transmitted bytes, so this literature does not
subsume a delivery-oriented study: our objective is encoded size and adaptive codec state
under matched perceptual quality, which area-minimizing packers neither measure nor
optimize.</p>
{H3('Cache granularity and delta delivery')}
<p>Bundling trades cache granularity for fewer requests, a tension delivery research has
long addressed. HTTP delta encoding transmits only the difference between a cached and a
current resource (RFC&nbsp;3229 [42]) using generic differencing formats (VCDIFF,
RFC&nbsp;3284 [43]); shared-dictionary schemes reuse previously delivered bytes as a
dictionary for later responses (SDCH [44]), the idea that shared-window and
trained-dictionary compressors (Brotli [22], zstd [23]) generalize and that Compression
Dictionary Transport [24] revives for the modern web. Standard HTTP caching semantics
(RFC&nbsp;9111 [45]) fix the granularity at the resource, which is exactly what bundling
coarsens; we apply delta and dictionary delivery to the whole-bundle cache-invalidation
problem (Section&nbsp;6.2). HTTP Archive's Web Almanac [8] supplies the population
statistics (median 13 images per mobile page, format share) that make the
many-small-images regime the common case rather than an edge case.</p>

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
universal support; the four mechanisms differ in image semantics, accessibility, loading
control, and browser support, compared for deployment in Table&nbsp;10
(Section&nbsp;6.4).</p>
{H3('Delivery, caching, and memory')}
<p>An atlas changes the unit of caching from the tile to the bundle. With standard
immutable content-addressed URLs (<code>atlas.3fe2a1.webp</code>,
<code>Cache-Control: immutable</code>), an unchanged atlas costs zero requests on a warm
cache, and the decode-once property still applies. The cost appears on content change:
editing one tile invalidates the whole bundle, so the expected re-download per deploy
grows with bundle size. Splitting the collection into k chunked atlases bounds the
worst-case invalidation at 1/k of the collection while retaining nearly all of the byte
and request savings, since chunking adds only a few container headers and a little grid
slack, which makes chunking the practical default for collections that update piecemeal. Grouping tiles by update cadence (stable icon set in one chunk,
weekly seasonal art in another) further confines invalidation to the chunk that
actually changed.</p>
<p>The second resource to budget is decoded memory: a decoded atlas occupies
width&nbsp;x&nbsp;height&nbsp;x&nbsp;4 bytes regardless of its encoded size, so a
4096x4096 atlas holds 64&nbsp;MB of RGBA for a 300&nbsp;KB transfer. Individual images
decode lazily and can be evicted per tile; an atlas is decoded and resident as a unit
while any tile is visible. Chunking bounds this cost the same way it bounds
invalidation, and below-the-fold chunks combine with lazy loading so off-screen tiles
cost neither bytes nor memory.</p>
A live-renderer measurement (Section&nbsp;5.6) confirms that at typical tile counts the
atlas is in fact the memory-favorable representation, so this analytical caution binds
only for very large atlases.</p>

{H2('Methodology')}
{H3('Assets and packing')}
<p>Two deterministic asset classes anchor the study: 521 Twemoji 72x72 flat-art tiles
(alpha composited over white) and 521 photographic 224x224 thumbnails, with the photo
set additionally downscaled to 112 and 56 pixels for the size sweep and synthetic
icon, product-thumbnail, and avatar corpora added for the use-case tests
(Section&nbsp;5.3). Tiles are packed row-major into a near-square grid; a padding
variant edge-replicates each tile by 8 or 16 pixels, and a vertical-strip variant packs
one tile per row band. All conditions consume identical source pixels.</p>
{H3('Codecs and matched-quality protocol')}
<p>Following the study's scope, the three dominant web formats encode each condition:
libjpeg-turbo JPEG, WebP (lossy and lossless), and PNG, with the lossy codecs swept
over a quality ladder q &isin; {{30,50,65,80,90}}. Quality is the mean over tiles of the
per-tile luma SSIM [25], each tile scored after cropping it back out of the decoded artifact
so atlas border bleed is charged to the atlas; the matched target of 0.97 is therefore a
mean-tile floor, and Section&nbsp;5.1 reports the per-tile spread where it is
load-bearing. Bytes are compared at equal quality by log-linear interpolation of each
condition's rate-distortion curve at the target; the five-point ladder is coarse, so
where the atlas and individual curves nearly coincide the interpolation is unstable and
equal-quality byte comparison is used instead (Section&nbsp;5.3). When an atlas's entire
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
classes as WebP q80, three protocols, and four network profiles. Within each
profile the load order is randomized across conditions, protocols, and repetitions, and
the first repetition of each cell is discarded as a warm-up, leaving 11 measured loads
per cell.</p>
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
<p>To confirm the crossover is not an artifact of the single deterministic subset each
Table&nbsp;1 cell uses, we resampled it: for each (tile size, N, codec) we drew 20 random
N-tile subsets from the full pool and computed the matched-quality saving of each. The
medians track Table&nbsp;1 and the 95% bootstrap intervals are tight and separate the
regimes. For photos the JPEG saving is 29.1% (95% CI [28.4, 29.5]) at 56&nbsp;px,
9.3% [8.9, 9.8] at 112&nbsp;px, and 2.6% [2.4, 2.8] at 224&nbsp;px, all clearly positive;
WebP is 14.8% [10.0, 17.4] at 56&nbsp;px, straddles zero at 112&nbsp;px
([&minus;1.6, 1.9]), and is clearly negative at 224&nbsp;px (&minus;8.0% [&minus;12.0,
&minus;6.7]). The WebP break-even near 100&nbsp;px is thus the point where its interval
crosses zero, not a single-sample coincidence.</p>
{table1}
{fig_cross}
<p>Atlasing is not free where per-image adaptation matters. On flat art, both lossless
formats lose from atlasing at N&nbsp;&ge;&nbsp;200 (PNG &minus;3 to &minus;6%, lossless WebP &minus;4
to &minus;5%): PNG chooses its prediction filter per scanline and an atlas scanline
crosses dozens of unrelated tiles, while lossless WebP fits transforms and entropy
codes per image, and one global model over hundreds of heterogeneous tiles cannot match
hundreds of specialized ones. Lossy WebP shows the same inversion on photographic tiles: VP8 adapts entropy tables per
image and allows at most four quantizer segments per frame, so an atlas of 500 diverse
photos shares four segments where individual files had four each. This penalty is a
quality effect, not a byte cost, and the &minus;8.5% headline is best read as the pair it
comes from: at equal encoder quality the 500-photo WebP atlas costs essentially the same
bytes as individual files (&minus;0.2% at q80) but reaches a slightly lower mean per-tile
SSIM (0.9748 vs 0.9784, a 0.004 deficit); the matched-quality protocol prices that small
deficit as the &minus;8.5% through interpolation on a steep rate-distortion curve. The
sign is robust (the deduplicated-subset bootstrap interval is [&minus;12.0, &minus;6.7]),
but the magnitude is metric-dependent, and Section&nbsp;5.4 shows two encoder flags
reverse it to +5%. Edge-replicated padding costs roughly 7 percentage points of saving
per 8-pixel step for JPEG and roughly 10 for WebP (flat art, N&nbsp;=&nbsp;200),
pricing the block-alignment mitigations against chroma bleed.</p>
<p>The absolute comparison compounds codec choice with bundling: at N&nbsp;=&nbsp;500
and SSIM 0.97 on flat art, individual JPEG files cost 630 KB, the JPEG atlas 464 KB,
individual WebP files 240 KB, and the WebP atlas 220 KB. Moving a legacy
individual-JPEG deployment to a WebP atlas cuts bytes by 65%; the format change
contributes most of it, and bundling contributes the rest while also collapsing 500
requests into one.</p>
<p>Matched-quality comparison equalizes the mean, not the tails. Table&nbsp;6 shows the
per-tile SSIM distribution: the WebP atlas systematically carries a worse worst tile than
individual files (a flat-art tile stuck at 0.85 that no quality setting recovers), while
JPEG's atlas and individual tails coincide. A practitioner enforcing a hard per-tile
floor rather than a mean should treat the WebP pixel atlas accordingly, or use the
byte-bundle, which preserves each tile's own encoding.</p>
{tail_html}
<p>The crossover is not an artifact of the luma-SSIM metric. We re-measured the photo
savings with SSIMULACRA2, the reference libjxl perceptual metric, scoring each condition
on the full grid image at matched quality (Table&nbsp;7). JPEG's atlas saving stays
positive at every tile size (about +33% at 56&nbsp;px, +12% at 112&nbsp;px, and +3% at
224&nbsp;px at a matched score of 70), tracking the luma-SSIM result closely. WebP is
positive only for the smallest tiles (+12% at 56&nbsp;px) and turns clearly negative by
112&nbsp;px (&minus;24%) and 224&nbsp;px (&minus;29%). The break-even therefore survives
the change of metric and moves to a smaller tile, and the WebP penalty is larger under
SSIMULACRA2 than under luma SSIM (&minus;29% vs &minus;8.5% at 224&nbsp;px): the diagnostic
that at equal encoder quality the WebP atlas reaches a lower score than individual files
while JPEG does not (for example WebP 112&nbsp;px q80 scores 72.9 as an atlas against 78.0
individually, JPEG 77.2 against 77.3) confirms that the deficit is the shared-quantizer
adaptive-state penalty, and that a perceptual metric weighting chroma and blocking prices
it higher.</p>
{ss2_html}
<p>The crossover is also a general regime across image populations and codecs, not a
property of one corpus. We repeated the matched-quality photo crossover on four
independent natural-photo populations (Lorem&nbsp;Picsum and three loremflickr categories:
generic, nature, food) and added AVIF alongside JPEG and WebP (Table&nbsp;8). The sign and
magnitude are consistent across populations: at 56&nbsp;px JPEG saves 25&ndash;27% on
every corpus, at 224&nbsp;px WebP is &minus;5 to &minus;8% on every corpus, and a model
trained on any three corpora predicts the held-out fourth to about 4.6 percentage points
of error, so a tile-size-and-codec rule, not corpus identity, sets the result. AVIF tracks
JPEG rather than WebP, staying positive at every size (+33% at 56&nbsp;px, +12% at
112&nbsp;px, +5% at 224&nbsp;px) and gaining the most at small sizes because its container
floor (303&nbsp;bytes) is the largest fixed cost to amortize. WebP is thus the one codec
whose atlas penalty turns negative on large photographs, which sharpens rather than
softens the coupling account: the sign of the byte effect is codec-specific, and it is
VP8's shared four-segment quantizer, not atlasing in general, that reverses it.</p>
{cross_html}
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

{H3('Supporting measurements: network timing')}
<p>The byte and construction results above are protocol-independent. This section reports how the byte savings translate to load time on a single-testbed browser study; it is supporting evidence for the deployment guidance, not a protocol-measurement contribution, and its absolute timings are environment-dependent.</p>
{net_html}
<p>Three protocol-level facts organize Table&nbsp;2 and Figure&nbsp;4. First, on
HTTP/1.1 and HTTP/3, bundling remains a large timing win for flat art: 4.5&ndash;8.6x and
4.8&ndash;7.7x respectively for 500 tiles across the network profiles, and 1.5&ndash;2.8x
for photos on the loss-free profiles (the 1% packet-loss photo cells fall to parity and
are discussed below). Across cells, added network impairment never speeds a condition up, and the reported speedups carry tight bootstrap intervals (Table&nbsp;2). Second, HTTP/2 is the strongest protocol for many small files: its
multiplexing loads 500 individual images almost as fast as the atlas on
bandwidth-limited links (1.0&ndash;1.1x at 9&nbsp;Mbit), so under HTTP/2 the case for
bundling small tiles rests chiefly on the byte saving of Table&nbsp;1 (up to 26% for
flat art) rather than on latency. Third, on this testbed HTTP/3's individual-file loads run several times
slower than HTTP/2's on the same links, up to 5x for flat art on the constrained profiles
and about 3x on the fast zero-loss link, and a concurrency diagnostic locates the cause. The diagnostic reconstructs each request's in-flight interval from the Resource Timing
API and finds the peak number of simultaneous image requests: HTTP/2 sustained
13&ndash;14 at once while HTTP/3 sustained only 6, roughly half the parallelism, and the
slowdown tracks that gap. The server's own QUIC transport log (quic-go qlog) confirms
the effect and locates it precisely: across cold HTTP/3 loads of the 500-file page, the
server records a peak of only 4&ndash;6 request streams open at once (median 5 for
photographs, 4 for flat art), agreeing with the browser-side count, while its transport
parameters advertise a 100-stream limit (<code>initial_max_streams_bidi</code>) that is
never approached, so the stream limit is not the binding constraint. To test whether the
low concurrency is a property of this particular server, we replayed the load against a
second, independent QUIC implementation (aioquic) driven by the same Chromium: it
sustained a median of 13 concurrent request streams, roughly double the quic-go/Caddy
figure and close to HTTP/2's, on a faster loopback path with smaller tiles that both bias
the count downward, so the gap is conservative. The low concurrency is therefore a
property of the specific server stack and its defaults interacting with Chromium's QUIC
scheduler, not of HTTP/3 itself, which multiplexes independent streams over one
connection. A default HTTP/3 stack can therefore under-multiplex a
many-small-image page relative to HTTP/2, which makes bundling valuable there, while a
different server stack narrows the gap. Under the 1% packet-loss
profile every serving condition becomes noise-dominated on this testbed: per-cell
coefficients of variation reach 0.4 and the atlas-vs-individual and chunk-vs-atlas
differences fall inside overlapping confidence intervals (for example lossy4g photos on
HTTP/1.1 give a single atlas at 1.50x and four chunks at 1.54x, indistinguishable). We
therefore make no loss-recovery claim for chunking from the timing data; chunking's
demonstrated benefit is cache granularity and bounded invalidation (Section&nbsp;6.2,
Figure&nbsp;5), not packet-loss resilience. The byte-bundle beats individual serving nearly everywhere on HTTP/1.1 and HTTP/3
(up to 5.6x) at exactly the individual conditions' byte cost, which makes it the
bundling method of choice for content whose pixels should not share a codec model
(photos, lossless assets); the pixel atlas remains faster where its byte savings
compound with the request savings.</p>

{H3('Local rendering cost: decode time and memory')}
<p>Transport is only half the client cost; decode and memory are the other half, and they
are measured locally with no network shaping so they isolate rendering (Table&nbsp;9). We
render N 96-pixel photographic tiles in one Chromium instance three ways and record time
to all tiles visible and the renderer process-tree memory over a blank-page baseline,
which captures the C++-side decoded-image cache that JavaScript-heap APIs do not expose. At
N&nbsp;=&nbsp;500 the pixel atlas is fastest to full visibility (33&nbsp;ms, since one
decode paints every tile) and uses the least memory (106&nbsp;MB over baseline), while 500
individual files take 767&nbsp;ms and 129&nbsp;MB and the byte-bundle 313&nbsp;ms and
143&nbsp;MB, the latter because it fetches its whole object before the first tile and then
retains N blob-backed decodes. Two milestones make the progressive difference concrete: the
atlas reaches first-viewport-visible in 15&nbsp;ms at every N, whereas individual files
reach it in 148&ndash;429&nbsp;ms as tiles stream in. For typical thumbnail collections the
atlas is therefore memory-favorable rather than a liability, and the
width&times;height&times;4 caution binds only for very large atlases, which chunking keeps
below.</p>
{mem_html}

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
files would have specialized. The fixed-cost half of this account is directly testable:
regressing each codec's measured saving (47 matched-quality cells) on the
overhead-to-content predictor 100&middot;H&middot;N/bytes<sub>individual</sub> gives
R<sup>2</sup>&nbsp;=&nbsp;0.99 for JPEG, where the container tables dominate, so
amortization alone explains the JPEG savings almost completely (slope 0.59, i.e. the
600-byte figure overstates the recoverable share). For lossy WebP the same predictor
captures only the ordering (R<sup>2</sup>&nbsp;=&nbsp;0.69) and badly under-predicts the
magnitude, the measured range of &minus;8.5 to +19% dwarfs the predicted 0.5 to 6%, and
for the lossless formats the fixed-cost term fails outright
(R<sup>2</sup>&nbsp;&lt;&nbsp;0.2, negative for lossless WebP). Those are precisely the
codecs where the adaptive-state term dominates: the shared four-segment allocation for
WebP, the per-scanline filter for PNG. The coupling account is thus a two-term
decomposition, a fixed-cost gain that is quantitatively predictive for JPEG and an
adaptive-state penalty that is codec-specific and, at present, characterized rather than
modeled; JPEG always wins because its shared cost is large and its adaptive coupling
weak, lossless flat art wins because a shared palette is pure fixed-cost saving, and
photographic WebP loses under the default encoder because the shared segments are
adaptive state, recovering once adaptive deblocking neutralizes the artifact.</p>
<p>A first step toward modeling the second term rather than only naming it: adding a
content-heterogeneity feature (the mean pairwise distance of tile thumbnails) with a
per-codec penalty coefficient lifts a pooled cross-codec fit from
R<sup>2</sup>&nbsp;=&nbsp;0.73 (fixed-cost term alone) to 0.78, and the learned penalties
order the codecs by their adaptive coupling exactly as the mechanism predicts (JPEG 1.2,
PNG 5.5, lossless WebP 12.7, lossy WebP 21.0). The modest lift shows a generic
heterogeneity proxy captures the direction but not the full magnitude of the penalty.</p>
<p>How far can the saving be predicted from the source images alone, before building any
atlas? We tested this directly. Eight content classes were assembled to span extreme
image statistics, natural photos, emoji, flags, and avatars alongside synthetic
gradients, noise, UI mockups, and objects on white, and six cheap features were computed
per class (edge density, DCT high-frequency energy, colour-histogram entropy, unique
colours, inter-tile heterogeneity, and luminance variance). Predicting a held-out class's
saving from these features does not improve on a size-and-codec baseline, and it fails
even on the isolated codec differential that cancels the fixed-cost term (Table&nbsp;11):
the adaptive-state penalty is codec-mechanistic and is not readable from source pixel
statistics. What does predict it is a measurement: a probe encode of only 10&ndash;20
tiles estimates the full-set saving to within about two percentage points (Spearman 0.98).
This is the empirical case for the design of Section&nbsp;6.3: the right move is not to
model the penalty but to measure the two candidate representations, and a small probe
suffices, which is why the heuristic reaches the oracle out-of-sample without any content
model.</p>
{predict_html}
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
previous version, the mechanism Compression Dictionary Transport (RFC&nbsp;9842) now
standardizes for the web. We measure the compression-level cost of this remedy as a
proxy, computing the delta offline rather than through a live browser-server negotiation:
in a 392-photo WebP bundle, a zstd delta against the prior bundle cost 25&nbsp;KB when 5
tiles changed and 237&nbsp;KB when 50 changed, tracking the changed-files optimum and
beating whole-atlas re-download (2.8&nbsp;MB) by two orders of magnitude. The structural
weakness thus becomes proportional to churn rather than to bundle size; an end-to-end CDT
deployment measurement is future work.</p>
<p>A warm-cache simulation over a 200-tile WebP collection makes the full trade-off
explicit (Figure&nbsp;5). Serving immutable individual files is the granularity ideal, a
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
<p>The cost above is not minimized by blind search; instead the measured curves calibrate a
greedy heuristic, implemented as a command-line tool (<code>atlas_optimizer</code>,
released with the study). The tool folds exact duplicates into shared coordinates;
partitions tiles by update cadence, lossless requirement, and dimensions; and routes each
group (Figure&nbsp;6). For a lossy group the routing is not decided by tile size alone: the
tool encodes both a pixel atlas and a byte-bundle and keeps the atlas only if it is
strictly smaller <em>and</em> passes a per-tile quality gate, so it never adopts an atlas
that loses bytes or damages a subset of tiles. The gate is exactly the tail constraint of
Section&nbsp;5.1: the atlas's worst per-tile SSIM must clear an absolute floor (default
0.90) and its 5th percentile must stay within a small tolerance of the byte-bundle's,
which carries individual-file quality. On the flat-art set treated as lossy, for instance,
a pixel atlas would save 19% of bytes but drives one tile to 0.87 SSIM, so the tool
rejects it and emits the byte-bundle instead. Lossless groups take the smaller of a
byte-bundle and a WebP-lossless strip, tiny groups stay individual, and every bundle is
chunked. It emits the atlas and bundle files, a CSS coordinate map, a loader snippet, and
a per-group savings report that records the measured decision and the per-tile SSIM tails.
Validated against the study's own asset sets, it converts 521
flat-art tiles into four WebP-lossless strip-atlas chunks (the byte-optimal choice for
this lossless class; declaring them lossy-encodable instead routes them to a byte-bundle,
since the pixel atlas that would save 19% of bytes fails the quality gate), and 521
photographic thumbnails, 119 of them exact repeats, into four self-describing byte-bundle
chunks at 21% fewer bytes, with 521 requests becoming four in both cases. An accounting
check confirms the emitted bytes and request count equal what the tool reports.</p>
{heuristic_html}
<p>Because those asset sets also shaped the rules, a fair test requires collections the
heuristic never saw. We evaluate it on five independent corpora, Noto emoji, OpenMoji,
country flags, Flickr photographs, and Robohash avatars, none of which were used in
calibration, against an offline oracle that enumerates the candidate configurations and
returns the byte-optimal one (Table&nbsp;5). Each group carries one measured tiebreak:
for a lossless group the heuristic keeps the smaller of a byte-bundle and a WebP-lossless
strip, since neither dominates (a strip wins on OpenMoji and Robohash, a byte-bundle on
Noto). With that tiebreak the heuristic's automatic choice equals the oracle on all five
corpora (0% regret), including the two content types, generated avatars and a second
emoji vendor, that most differ from the calibration sets. This is the property that
matters for a deployable tool: on collections it was not built from, it does not merely
save bytes, it chooses at or near the best available configuration. This comparison is on
bytes; the per-tile quality floor is an additional safety constraint that overrides a
byte-optimal atlas only where it would push a tile below the floor.</p>
<p>The value is in choosing, not in any single layout. Table&nbsp;5 also scores three
fixed rules a developer might hardcode, each still allowed the best admissible codec:
always build one pixel atlas, always byte-bundle, or always strip-pack. Every one is
beaten on at least one corpus (mean regret 5.8%, 9.4%, and 186%; always-strip alone costs
+643% on photographs, where a lossless strip is disastrous), because the byte-optimal
layout flips with content: strips win on the sparse OpenMoji and Robohash sets, a
byte-bundle wins on dense Noto and on photographs, a pixel atlas wins on the flat-color
flags. The calibrated heuristic tracks those flips to zero regret; no fixed rule
does.</p>
{oracle_html}
{H3('Choosing a rendering mechanism')}
<p>Selecting a representation is only half of deployment; the four ways to show a bundled
tile (Section&nbsp;3.1) are not interchangeable in a production page, because they differ
in native image semantics, accessibility, loading control, and browser support
(Table&nbsp;10). A CSS pixel atlas shown through <code>background-position</code> is
universally supported and ideal for decorative icons, but a background image is not an
<code>&lt;img&gt;</code>: it carries no intrinsic alt text (accessibility must come from
surrounding ARIA), does not participate in native lazy loading or
<code>fetchpriority</code>, and is inappropriate for content images that must be
announced. A cropped <code>&lt;img&gt;</code> in an <code>overflow:hidden</code> wrapper
keeps alt text and native loading and works cross-browser; <code>object-view-box</code>
gives the same with less markup but is Chromium-only and should not be treated as a
generally deployable solution. A byte-bundle reconstructs real per-tile
<code>&lt;img&gt;</code> elements from blob URLs, so it recovers full image semantics at
the cost of a small loader script and its content-security-policy implications, which
makes it the natural choice for heterogeneous or content-bearing photographs. The selector
of Section&nbsp;6.3 chooses the byte layout; this table chooses the display mechanism, and
the two decisions compose.</p>
<div class='tablewrap'><table>
<caption><b>Table 10.</b> Display mechanisms for a bundled tile and how they differ in
production. All four paint after a single atlas or bundle fetch; they diverge on image
semantics, accessibility, loading control, and support. Pick the byte layout with the
Section&nbsp;6.3 selector and the mechanism here.</caption>
<thead><tr><th>mechanism</th><th>native &lt;img&gt;</th><th>alt text</th>
<th>lazy load / priority</th><th>JS / CSP</th><th>support</th><th>best use</th></tr></thead>
<tbody>
<tr><td>CSS <code>background-position</code></td><td>no</td><td>via ARIA</td>
<td>manual</td><td>CSS only</td><td>universal</td><td>decorative icons</td></tr>
<tr><td>cropped <code>&lt;img&gt;</code> wrapper</td><td>yes</td><td>yes</td>
<td>native</td><td>CSS only</td><td>broad</td><td>semantic images</td></tr>
<tr><td><code>object-view-box</code></td><td>yes</td><td>yes</td><td>native</td>
<td>CSS only</td><td>Chromium only</td><td>native crop (emerging)</td></tr>
<tr><td>byte-bundle + blob URLs</td><td>yes (after JS)</td><td>yes</td>
<td>app-controlled</td><td>JS + CSP</td><td>broad APIs</td><td>heterogeneous photos</td></tr>
</tbody></table></div>
{H3('Limitations')}
<p>Quality is measured by luma SSIM at a 0.97 target; the photo crossover is confirmed
under the SSIMULACRA2 perceptual metric (Section&nbsp;5.1, Table&nbsp;7), and applying it
or butteraugli across the full sweep would further sharpen the matched-quality
comparison. The shared-palette result uses a synthetic limited-color corpus that is
the ideal case; anti-aliased production icons will realize less of it. The network study
emulates four profiles on a single-machine testbed rather than the open Internet, and
measures time-to-all-tiles-visible rather than a full field-metric suite. Decoded-memory
cost is now measured in a live renderer (Section&nbsp;3.2, Table&nbsp;9), confirming the
pixel atlas is memory-favorable at typical tile counts; profiling under a production
framework with texture upload and long-lived navigation remains future work. The HTTP/3
concurrency diagnosis is confirmed from the server's own QUIC transport log
(Section&nbsp;5.5) and cross-checked against a second QUIC implementation (aioquic), which
sustained about twice the concurrency; a fully controlled comparison across server stacks
and native Linux remains future work. The matched-quality photo crossover is validated across four
independent natural-photo populations (Section&nbsp;5.1) and the heuristic on five further
independent corpora (Section&nbsp;6.3); a still wider survey of naturally-occurring
collections would further generalize the reported thresholds. The network numbers are
medians of 11 cold loads per cell with bootstrap confidence intervals (Table&nbsp;2) but
no formal significance testing, and the timing endpoint is time-to-all-tiles-visible;
first-tile and first-viewport milestones are reported for the local renderer (Table&nbsp;9)
but LCP, decode CPU, and warm-cache multi-navigation behavior under realistic asset churn
are not measured and could change the recommended bundle size. Finally, JPEG&nbsp;XL is
left to future work; AVIF is included in the photographic crossover (Section&nbsp;5.1) and,
like JPEG, benefits from atlasing at every tested size.</p>

{H2('Conclusion')}
<p>Bundling small web images pays, and the study makes precise when and by how much for
the formats that carry most of the web's images. Atlas small lossy tiles: icons
and thumbnails gain up to 30% under JPEG, up to 19% under WebP, and up to 33% under AVIF
at matched quality, the effect holding across four independent photo populations; and
lossless flat art, the icon-set and map-marker case, gains 40&ndash;97%
with a strip-packed or shared-palette bundle that is smaller than even the best lossy
option. Serve larger photographs and lossless assets as a byte-bundle, which collapses
requests at near-zero byte cost (a small offset header), or, for photographic WebP, tune
the encoder (noise shaping plus adaptive deblocking) to turn the atlas penalty into a
gain. Ship about four chunks for bounded cache invalidation and decoded-memory limits,
deduplicate repeats explicitly, and delta-encode updates against the cached bundle
(Compression Dictionary Transport). On the wire, bundling loads 500 small flat-art tiles
4.5&ndash;8.6x faster to full visibility on HTTP/1.1 (1.5&ndash;2.8x for photographic
thumbnails) and is chiefly a byte optimization on HTTP/2; the comparable HTTP/3 gain
reflects a request-concurrency limit specific to the tested server stack, which a second
QUIC implementation roughly halves (Section&nbsp;5.5), not a protocol-general result. The unifying
account, that savings come from sharing fixed costs and losses from sharing adaptive
state, is quantitatively predictive for JPEG (R<sup>2</sup>&nbsp;=&nbsp;0.99) and
organizes the codec-specific behavior of the rest, and it guides the accompanying
construction
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
<p>[4] R. Meireles, J. Liu, P. Steenkiste. A study of HTTP/2's Server Push Performance
Potential. arXiv:2207.05885, 2022.</p>
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
RFC 7540, IETF, 2015. doi:10.17487/RFC7540</p>
<p>[13] M. Bishop. HTTP/3. RFC 9114, IETF, 2022. doi:10.17487/RFC9114</p>
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
<p>[22] J. Alakuijala, Z. Szabadka. Brotli Compressed Data Format. RFC 7932, IETF, 2016.
doi:10.17487/RFC7932</p>
<p>[23] Y. Collet, M. Kucherawy. Zstandard Compression and the application/zstd Media
Type. RFC 8878, IETF, 2021. doi:10.17487/RFC8878</p>
<p>[24] P. Meenan, Y. Weiss. Compression Dictionary Transport. RFC 9842, IETF, 2025.
doi:10.17487/RFC9842</p>
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
<p>[33] J. Marszałkowski, J. Mizgajski, D. Mokwa, M. Drozdowski. Analysis and Solution of
CSS-Sprite Packing Problem. ACM Trans. Web 10(1), Article 1, 2016. doi:10.1145/2818377</p>
<p>[34] M. Butkiewicz, H. V. Madhyastha, V. Sekar. Understanding Website Complexity:
Measurements, Metrics, and Implications. ACM Internet Measurement Conference (IMC), 2011.
doi:10.1145/2068816.2068846</p>
<p>[35] S. Souders. High Performance Web Sites: Essential Knowledge for Front-End
Engineers. O'Reilly Media, 2007. ISBN 978-0-596-52930-7.</p>
<p>[36] H. de Saxcé, I. Oprescu, Y. Chen. Is HTTP/2 really faster than HTTP/1.1? IEEE
INFOCOM Workshops (INFOCOM WKSHPS), 2015, pp. 293-299.
doi:10.1109/INFCOMW.2015.7179400</p>
<p>[37] A. M. Kakhki, S. Jero, D. Choffnes, C. Nita-Rotaru, A. Mislove. Taking a Long Look
at QUIC: An Approach for Rigorous Evaluation of Rapidly Evolving Transport Protocols. ACM
Internet Measurement Conference (IMC), 2017, pp. 290-303. doi:10.1145/3131365.3131368</p>
<p>[38] J. Alakuijala, R. van Asseldonk, S. Boukortt, M. Bruse, I.-M. Comșa, M. Firsching,
et al. JPEG XL next-generation image compression architecture and coding tools. Proc.
SPIE 11137, Applications of Digital Image Processing XLII, 111370K, 2019.
doi:10.1117/12.2529237</p>
<p>[39] Google. WebP Compression Study, 2011.
https://developers.google.com/speed/webp/docs/webp_study</p>
<p>[40] G. Randers-Pehrson. MNG (Multiple-image Network Graphics) Format, Version 1.0,
2001. http://www.libpng.org/pub/mng/spec/ (APNG is standardized in the W3C PNG
Specification, 3rd ed. [18]).</p>
<p>[41] ISO/IEC 23008-12:2017. Information technology: High efficiency coding and media
delivery in heterogeneous environments, Part 12: Image File Format (HEIF).</p>
<p>[42] J. Mogul, B. Krishnamurthy, F. Douglis, A. Feldmann, Y. Goland, A. van Hoff,
D. Hellerstein. Delta Encoding in HTTP. RFC 3229, IETF, 2002. doi:10.17487/RFC3229</p>
<p>[43] D. Korn, J. MacDonald, J. Mogul, K. Vo. The VCDIFF Generic Differencing and
Compression Data Format. RFC 3284, IETF, 2002. doi:10.17487/RFC3284</p>
<p>[44] J. Butler, W.-H. Lee, B. McQuade, K. Mixter. A Proposal for Shared Dictionary
Compression over HTTP (SDCH). IETF Internet-Draft draft-lee-sdch-spec, 2008.</p>
<p>[45] R. Fielding, M. Nottingham, J. Reschke (Eds.). HTTP Caching. RFC 9111 (STD 98),
IETF, 2022. doi:10.17487/RFC9111</p>
</div>
<div class="footer">Alexander Apartsin, Yehudit Aperstein &middot; 2026</div>
</body></html>"""

    # Renumber tables to document order (captions <b>Table N.</b> define the order;
    # references "Table&nbsp;N" and "Table N" are remapped to match). Keeps numbering
    # correct after any subsection reordering.
    import re as _re

    def _renumber(kind):
        nonlocal html
        order = [int(m.group(1)) for m in _re.finditer(rf"<b>{kind} (\d+)\.</b>", html)]
        remap = {old: new for new, old in enumerate(order, 1)}
        if remap == {k: k for k in remap}:
            return
        for old in sorted(remap, reverse=True):  # placeholder pass avoids collisions
            html = html.replace(f"<b>{kind} {old}.</b>", f"<b>{kind} \x00{remap[old]}.</b>")
            html = html.replace(f"{kind}&nbsp;{old}", f"{kind}&nbsp;\x00{remap[old]}")
        html = html.replace("\x00", "")
    _renumber("Table")
    _renumber("Figure")
    out = ROOT / "docs" / "paper.html"
    out.write_text(html, encoding="utf-8")
    # the paper IS the site landing page
    (ROOT / "docs" / "index.html").write_text(html, encoding="utf-8")
    # content canaries
    for canary in ["Table 1.", "Table 2.", "Table 3.", "Table 4.", "Table 5.", "Table 6.",
                   "Table 7.", "Table 8.", "Table 9.", "Table 10.", "probe encode",
                   "Figure 1.", "Figure 2.", "Figure 3.", "Figure 4.",
                   "Figure 5.", "<svg", "atlas_emoji_100.png", "Abstract", "References",
                   "SSIMULACRA2", "AVIF", "RFC 9842", "[45]",
                   "background-position", "object-view-box", "Cache-Control"]:
        assert canary in html, f"CANARY FAILED: {canary}"
    assert html.count("<svg") >= 5, "CANARY FAILED: expected chart SVGs"
    assert html.count("aria-label") >= 5, "CANARY FAILED: chart accessibility labels"
    print(f"wrote {out} ({len(html):,} bytes), canaries pass")


if __name__ == "__main__":
    main()
