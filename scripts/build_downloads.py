"""Regenerate the downloadable PDF and DOCX of the paper from docs/paper.html.

Run after build_paper.py so the linked download files (docs/paper.pdf, docs/paper.docx)
track the HTML. The PDF is a faithful Chromium print of the page (vector SVG figures,
house CSS; the on-page download bar is hidden by @media print). The DOCX rasterizes the
inline SVG charts to PNG at 2x, embeds the atlas image, keeps every HTML table as a real
Word table, and converts via pandoc.

Requires: Playwright (chromium) and pandoc on PATH.
"""
import re
import subprocess
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
HTML = ROOT / "docs" / "paper.html"
PDF = ROOT / "docs" / "paper.pdf"
DOCX = ROOT / "docs" / "paper.docx"


def build_pdf(pw):
    b = pw.chromium.launch()
    pg = b.new_page()
    pg.goto(HTML.as_uri(), wait_until="networkidle")
    pg.emulate_media(media="print")
    pg.pdf(path=str(PDF), format="A4", print_background=True,
           margin={"top": "14mm", "bottom": "14mm", "left": "14mm", "right": "14mm"})
    b.close()
    print(f"wrote {PDF} ({PDF.stat().st_size:,} B)")


def build_docx(pw, figdir):
    html = HTML.read_text(encoding="utf-8")
    html = re.sub(r'<div class="downloads">.*?</div>', "", html, flags=re.S, count=1)
    svgs = re.findall(r"<svg.*?</svg>", html, re.S)
    b = pw.chromium.launch()
    ctx = b.new_context(device_scale_factor=2)
    pg = ctx.new_page()
    for i, s in enumerate(svgs):
        m = re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', s)
        w, h = (float(m.group(1)), float(m.group(2))) if m else (600, 400)
        pg.set_viewport_size({"width": int(w) + 4, "height": int(h) + 4})
        pg.set_content(f'<body style="margin:2px;background:#fff">'
                       f'<div style="width:{w}px;height:{h}px">{s}</div></body>')
        pg.wait_for_timeout(120)
        png = figdir / f"svg{i}.png"
        pg.locator("div").first.screenshot(path=str(png))
        html = html.replace(s, f'<img src="{png.as_uri()}"/>', 1)
    b.close()
    atlas = (ROOT / "docs" / "img" / "atlas_emoji_100.png").as_uri()
    html = html.replace("src='img/atlas_emoji_100.png'", f"src='{atlas}'")
    tmp = figdir / "paper_docx.html"
    tmp.write_text(html, encoding="utf-8")
    subprocess.run(["pandoc", str(tmp), "-f", "html", "-o", str(DOCX),
                    "--metadata", "title=Image Bundling Revisited"], check=True)
    print(f"wrote {DOCX} ({DOCX.stat().st_size:,} B)")


def main():
    with tempfile.TemporaryDirectory() as td:
        figdir = Path(td)
        with sync_playwright() as pw:
            build_pdf(pw)
            build_docx(pw, figdir)
    print("downloads built")


if __name__ == "__main__":
    main()
