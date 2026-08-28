"""Render docs/results-phase1.html from matched_quality_savings.json files.

Usage: python make_results_page.py phase1_emoji phase1_photos
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FAMS = ["jpeg", "webp", "avif", "jxl", "png", "webp_ll", "jxl_ll"]
COLORS = {"jpeg": "#c0392b", "webp": "#2980b9", "avif": "#8e44ad", "jxl": "#27ae60",
          "png": "#7f8c8d", "webp_ll": "#16a085", "jxl_ll": "#d35400"}


NSHADES = {10: "#c6d3e0", 50: "#8fa8c0", 200: "#4f7196", 500: "#14385c"}
SHORT = {"avif": "AVIF", "jpeg": "JPEG", "jxl": "JPEG XL", "webp": "WebP",
         "png": "PNG", "webp_ll": "WebP-ll", "jxl_ll": "JXL-ll"}


def bar_chart(rows, cls, target, pad, panel_label="", group_by="codec"):
    """Grouped bar chart of savings%. group_by='codec': codec groups, N-shaded bars.
    group_by='n': N groups, codec-colored bars."""
    vals = {}
    for r in rows:
        lossless = r["ssim_target"] is None
        if r["class"] != cls or r["pad"] != pad:
            continue
        if not lossless and r["ssim_target"] != target:
            continue
        vals[(r["codec"], r["n"])] = r["saving_pct"]
    if not vals:
        return ""
    codecs = [c for c in FAMS if any(k[0] == c for k in vals)]
    ns = sorted({k[1] for k in vals})
    if group_by == "n":
        groups = [(n, [(c, vals.get((c, n))) for c in codecs]) for n in ns]
        glabels = [f"N={n}" for n in ns]
        color_of = {c: COLORS.get(c, "#333") for c in codecs}
        legend_items = [(SHORT.get(c, c), COLORS.get(c, "#333"), "line") for c in codecs]
        MRLEG = 96
    else:
        groups = [(c, [(n, vals.get((c, n))) for n in ns]) for c in codecs]
        glabels = [SHORT.get(c, c) for c in codecs]
        color_of = None
        legend_items = [(f"N={n}", NSHADES.get(n, "#333"), "rect") for n in ns]
        MRLEG = 96
    W, H, ML, MB, MT, MR = 520, 300, 56, 46, 16, MRLEG
    ymin = min(0, min(v for v in vals.values())) - 3
    ymax = max(vals.values()) + 3
    gw = (W - ML - MR) / len(groups)
    nbars = max(len(m) for _, m in groups)
    bw = min(13.0, (gw - 10) / nbars)

    def Y(s):
        return (H - MB) - (H - MB - MT) * (s - ymin) / (ymax - ymin)

    out = [f'<svg viewBox="0 0 {W} {H}" style="max-width:100%" '
           f'font-family="Georgia,serif" role="img" '
           f'aria-label="Bytes saved by atlasing per codec and image count, {cls}">']
    import math
    gstart = int(math.floor(ymin / 20) * 20)
    for g in range(gstart, int(ymax) + 1, 20):
        out.append(f'<line x1="{ML}" y1="{Y(g):.0f}" x2="{W-MR}" y2="{Y(g):.0f}" stroke="#eee"/>'
                   f'<text x="{ML-6}" y="{Y(g)+4:.0f}" font-size="10" text-anchor="end" '
                   f'fill="#5a626c">{g}</text>')
    for gi, (gkey, members) in enumerate(groups):
        x0 = ML + gi * gw + (gw - bw * len(members)) / 2
        for mi, (mkey, s) in enumerate(members):
            if s is None:
                continue
            fill = color_of[mkey] if group_by == "n" else NSHADES.get(mkey, "#333")
            x = x0 + mi * bw
            y0, y1 = Y(max(0, s)), Y(min(0, s))
            out.append(f'<rect x="{x:.1f}" y="{y0:.1f}" width="{bw-1.5:.1f}" '
                       f'height="{max(0.5, y1-y0):.1f}" fill="{fill}"/>')
        out.append(f'<text x="{ML+gi*gw+gw/2:.0f}" y="{H-MB+16}" font-size="10" '
                   f'text-anchor="middle" fill="#5a626c">{glabels[gi]}</text>')
    out.append(f'<line x1="{ML}" y1="{Y(0):.0f}" x2="{W-MR}" y2="{Y(0):.0f}" stroke="#999"/>')
    xlabel = "images per bundle" if group_by == "n" else "codec"
    out.append(f'<text x="{(ML+W-MR)/2:.0f}" y="{H-8}" font-size="11" text-anchor="middle" '
               f'fill="#111418">{xlabel}</text>')
    out.append(f'<text x="14" y="{(MT+H-MB)/2:.0f}" font-size="11" text-anchor="middle" '
               f'fill="#111418" transform="rotate(-90 14 {(MT+H-MB)/2:.0f})">'
               f'bytes saved by atlasing (%)</text>')
    if panel_label:
        out.append(f'<text x="{ML+6}" y="{MT+12}" font-size="12" font-weight="bold" '
                   f'fill="#111418">{panel_label}</text>')
    lx, ly, lh = W - MR + 12, MT + 6, 17
    out.append(f'<rect x="{lx-6}" y="{ly-12}" width="{MR-14}" '
               f'height="{len(legend_items)*lh+16}" fill="#fff" stroke="#d1d4d8"/>')
    for i, (label, color, _) in enumerate(legend_items):
        yy = ly + i * lh
        out.append(f'<rect x="{lx}" y="{yy-7}" width="12" height="10" fill="{color}"/>'
                   f'<text x="{lx+16}" y="{yy+2}" font-size="9" fill="#111418">{label}</text>')
    out.append('</svg>')
    return "".join(out)


def svg_chart(rows, cls, target, pad, panel_label=""):
    """Savings% vs N line chart, one line per codec, for one ssim target and padding.
    Includes axis titles, a boxed legend, and an optional panel label like '(a)'."""
    import math
    pts = {}
    for r in rows:
        lossless = r["ssim_target"] is None
        if r["class"] != cls or r["pad"] != pad:
            continue
        if not lossless and r["ssim_target"] != target:
            continue
        pts.setdefault(r["codec"], []).append((r["n"], r["saving_pct"]))
    if not pts:
        return ""
    W, H, ML, MB, MT, MR = 520, 300, 56, 46, 16, 150
    ns = sorted({n for v in pts.values() for n, _ in v})
    ymin = min(0, min(s for v in pts.values() for _, s in v)) - 3
    ymax = max(s for v in pts.values() for _, s in v) + 3

    def X(n):
        return ML + (W - ML - MR) * (math.log(n) - math.log(ns[0])) / (
            math.log(ns[-1]) - math.log(ns[0]) or 1)

    def Y(s):
        return (H - MB) - (H - MB - MT) * (s - ymin) / (ymax - ymin)

    out = [f'<svg viewBox="0 0 {W} {H}" style="max-width:100%" '
           f'font-family="Georgia,serif" role="img" '
           f'aria-label="Bytes saved by atlasing vs image count, {cls}">']
    # gridlines + y tick labels
    gstart = int(math.floor(ymin / 10) * 10)
    for g in range(gstart, int(ymax) + 1, 10):
        out.append(f'<line x1="{ML}" y1="{Y(g):.0f}" x2="{W-MR}" y2="{Y(g):.0f}" stroke="#eee"/>'
                   f'<text x="{ML-6}" y="{Y(g)+4:.0f}" font-size="10" text-anchor="end" '
                   f'fill="#5a626c">{g}</text>')
    out.append(f'<line x1="{ML}" y1="{Y(0):.0f}" x2="{W-MR}" y2="{Y(0):.0f}" stroke="#999"/>')
    # x ticks
    for n in ns:
        out.append(f'<line x1="{X(n):.0f}" y1="{H-MB}" x2="{X(n):.0f}" y2="{H-MB+4}" stroke="#999"/>'
                   f'<text x="{X(n):.0f}" y="{H-MB+16}" font-size="10" text-anchor="middle" '
                   f'fill="#5a626c">{n}</text>')
    # axis titles
    out.append(f'<text x="{(ML+W-MR)/2:.0f}" y="{H-8}" font-size="11" text-anchor="middle" '
               f'fill="#111418">images per bundle, N (log scale)</text>')
    out.append(f'<text x="14" y="{(MT+H-MB)/2:.0f}" font-size="11" text-anchor="middle" '
               f'fill="#111418" transform="rotate(-90 14 {(MT+H-MB)/2:.0f})">'
               f'bytes saved by atlasing (%)</text>')
    # panel label
    if panel_label:
        out.append(f'<text x="{ML+6}" y="{MT+12}" font-size="12" font-weight="bold" '
                   f'fill="#111418">{panel_label}</text>')
    # series
    order = [c for c in FAMS if c in pts]
    for codec in order:
        v = sorted(pts[codec])
        d = " ".join(f"{X(n):.1f},{Y(s):.1f}" for n, s in v)
        c = COLORS.get(codec, "#333")
        out.append(f'<polyline points="{d}" fill="none" stroke="{c}" stroke-width="2"/>')
        for n, s in v:
            out.append(f'<circle cx="{X(n):.1f}" cy="{Y(s):.1f}" r="2.5" fill="{c}"/>')
    # legend box
    LEG = {"jpeg": "JPEG", "webp": "WebP", "avif": "AVIF", "jxl": "JPEG XL",
           "png": "PNG (lossless)", "webp_ll": "WebP lossless", "jxl_ll": "JXL lossless"}
    lx, ly, lh = W - MR + 12, MT + 6, 17
    out.append(f'<rect x="{lx-6}" y="{ly-12}" width="{MR-14}" height="{len(order)*lh+16}" '
               f'fill="#fff" stroke="#d1d4d8"/>')
    for i, codec in enumerate(order):
        c = COLORS.get(codec, "#333")
        yy = ly + i * lh
        out.append(f'<line x1="{lx}" y1="{yy}" x2="{lx+18}" y2="{yy}" stroke="{c}" stroke-width="2"/>'
                   f'<circle cx="{lx+9}" cy="{yy}" r="2.5" fill="{c}"/>'
                   f'<text x="{lx+24}" y="{yy+4}" font-size="10" fill="#111418">{LEG.get(codec, codec)}</text>')
    out.append('</svg>')
    return "".join(out)


def main():
    tags = sys.argv[1:]
    rows = []
    for tag in tags:
        rows += json.load((ROOT / "results" / "static" / tag /
                           "matched_quality_savings.json").open())
    classes = sorted({r["class"] for r in rows})
    html = ["""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Phase 1 Results: Bytes Saved by Atlasing</title>
<style>body{font-family:system-ui,sans-serif;max-width:60rem;margin:2rem auto;padding:0 1rem;line-height:1.5;color:#1a1a2e}
h1{font-size:1.5rem}h2{font-size:1.2rem;margin-top:2rem}
table{border-collapse:collapse;font-size:0.85rem}td,th{border:1px solid #ddd;padding:3px 8px;text-align:right}
th{background:#f5f5f5}td:first-child,th:first-child{text-align:left}.neg{color:#c0392b}.pos{color:#1e8449}
.muted{color:#666;font-size:0.9rem}</style></head><body>
<h1>Phase 1: bytes saved by atlasing, at matched SSIM</h1>
<p class="muted">Each point compares one atlas (grid, pad=0 unless noted) against the same
tiles as individual files, at equal interpolated per-tile SSIM. Positive = atlas smaller.
<a href="https://github.com/ApartsinProjects/ImageBundling">Repo and methodology</a>.</p>"""]

    fignum = 0
    ex_file = ROOT / "docs" / "img" / "examples.json"
    if ex_file.exists():
        html.append("<h2>What an atlas looks like</h2>")
        for ex in json.load(ex_file.open()):
            s = ex["stats"]
            fignum += 1
            cap = "; ".join(
                f"{k}: {v['individual']:,} B as {ex['n']} files vs {v['atlas']:,} B "
                f"as one atlas ({v['saving_pct']:+.1f}%)" for k, v in s.items())
            html.append(
                f'<figure style="margin:1rem 0"><img src="img/{ex["file"]}" '
                f'style="max-width:100%;height:auto;border:1px solid #ddd" '
                f'alt="{ex["n"]}-tile {ex["class"]} atlas">'
                f'<figcaption class="muted"><b>Figure {fignum}.</b> '
                f'{ex["n"]} {ex["class"]} tiles '
                f'({ex["tile"]} px each) packed into one {ex["grid"]} grid, '
                f'{ex["atlas_px"]} px. Same encoder settings both ways: {cap}. '
                f'{ex["n"]} HTTP requests become 1; the page shows each tile with CSS '
                f'background-position.</figcaption></figure>')
    for cls in classes:
        fignum += 1
        html.append(f"<h2>{cls} (SSIM target 0.97, pad 0)</h2>")
        html.append(f'<figure style="margin:1rem 0">{svg_chart(rows, cls, 0.97, 0)}'
                    f'<figcaption class="muted"><b>Figure {fignum}.</b> Bytes saved by '
                    f'atlasing versus images-per-bundle N for the {cls} class, at matched '
                    f'per-tile SSIM 0.97 (lossy codecs) or exact lossless comparison, grid '
                    f'packing, no padding. Points above zero mean the atlas is smaller than '
                    f'the same tiles as individual files.</figcaption></figure>')
        html.append("<details><summary>Full table (all SSIM targets and paddings)</summary>")
        html.append("<table><tr><th>codec</th><th>n</th><th>pad</th><th>ssim</th>"
                    "<th>individual B</th><th>atlas B</th><th>saving</th></tr>")
        for r in sorted([r for r in rows if r["class"] == cls],
                        key=lambda r: (r["codec"], r["n"], r["pad"], str(r["ssim_target"]))):
            c = "pos" if r["saving_pct"] > 0 else "neg"
            html.append(f"<tr><td>{r['codec']}</td><td>{r['n']}</td><td>{r['pad']}</td>"
                        f"<td>{r['ssim_target'] or 'lossless'}</td><td>{r['bytes_individual']:,}</td>"
                        f"<td>{r['bytes_atlas']:,}</td><td class='{c}'>{r['saving_pct']:.1f}%</td></tr>")
        html.append("</table></details>")
    html.append('<p class="muted">Alexander Apartsin &middot; original project MPCode 2001 &middot; revisited 2026</p>')
    html.append("</body></html>")
    out = ROOT / "docs" / "results-phase1.html"
    out.write_text("\n".join(html), encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
