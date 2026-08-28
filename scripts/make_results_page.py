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


def svg_chart(rows, cls, target, pad):
    """Savings% vs N line chart, one line per codec, for one ssim target and padding."""
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
    W, H, ML, MB = 460, 260, 46, 30
    ns = sorted({n for v in pts.values() for n, _ in v})
    ymin = min(0, min(s for v in pts.values() for _, s in v)) - 3
    ymax = max(s for v in pts.values() for _, s in v) + 3

    def X(n):
        import math
        return ML + (W - ML - 10) * (math.log(n) - math.log(ns[0])) / (
            math.log(ns[-1]) - math.log(ns[0]) or 1)

    def Y(s):
        return (H - MB) - (H - MB - 10) * (s - ymin) / (ymax - ymin)

    out = [f'<svg viewBox="0 0 {W} {H}" style="max-width:100%">']
    for g in range(0, int(ymax) + 1, 10):
        out.append(f'<line x1="{ML}" y1="{Y(g):.0f}" x2="{W-10}" y2="{Y(g):.0f}" stroke="#eee"/>'
                   f'<text x="{ML-6}" y="{Y(g)+4:.0f}" font-size="10" text-anchor="end">{g}%</text>')
    out.append(f'<line x1="{ML}" y1="{Y(0):.0f}" x2="{W-10}" y2="{Y(0):.0f}" stroke="#999"/>')
    for n in ns:
        out.append(f'<text x="{X(n):.0f}" y="{H-12}" font-size="10" text-anchor="middle">{n}</text>')
    for codec, v in pts.items():
        v = sorted(v)
        d = " ".join(f"{X(n):.1f},{Y(s):.1f}" for n, s in v)
        c = COLORS.get(codec, "#333")
        out.append(f'<polyline points="{d}" fill="none" stroke="{c}" stroke-width="2"/>')
        lx, ly = X(v[-1][0]), Y(v[-1][1])
        out.append(f'<text x="{lx+3:.0f}" y="{ly+3:.0f}" font-size="10" fill="{c}">{codec}</text>')
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

    ex_file = ROOT / "docs" / "img" / "examples.json"
    if ex_file.exists():
        html.append("<h2>What an atlas looks like</h2>")
        for ex in json.load(ex_file.open()):
            s = ex["stats"]
            cap = "; ".join(
                f"{k}: {v['individual']:,} B as {ex['n']} files vs {v['atlas']:,} B "
                f"as one atlas ({v['saving_pct']:+.1f}%)" for k, v in s.items())
            html.append(
                f'<figure style="margin:1rem 0"><img src="img/{ex["file"]}" '
                f'style="max-width:100%;height:auto;border:1px solid #ddd" '
                f'alt="{ex["n"]}-tile {ex["class"]} atlas">'
                f'<figcaption class="muted">{ex["n"]} {ex["class"]} tiles '
                f'({ex["tile"]} px each) packed into one {ex["grid"]} grid, '
                f'{ex["atlas_px"]} px. Same encoder settings both ways: {cap}. '
                f'{ex["n"]} HTTP requests become 1; the page shows each tile with CSS '
                f'background-position.</figcaption></figure>')
    for cls in classes:
        html.append(f"<h2>{cls} (SSIM target 0.97, pad 0)</h2>")
        html.append(svg_chart(rows, cls, 0.97, 0))
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
