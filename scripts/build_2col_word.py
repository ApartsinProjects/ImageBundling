"""Build the two-column Word deliverables from docs/paper.html via the html2doc skill.

  docs/paper-2col.docx       two-column Word document (editable)
  docs/paper-2col-word.pdf   PDF render of that document (LibreOffice headless)

Pipeline: katex_to_mathml (no-op here, no KaTeX) -> convert_to_docx (--profile
two-column) -> apply_academic_style (--profile two-column). The DOCX->PDF render
uses LibreOffice so it does not require Word. Run after build_paper.py.
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL = Path(r"C:\Users\apart\.claude\skills\html2doc")
SCRATCH = Path(r"E:\tmp\claude\E--Projects-ImageBudnling"
               r"\67b7b589-2b72-4287-8c11-331d55592201\scratchpad")
PY = sys.executable
SOFFICE = Path(r"C:\Program Files\LibreOffice\program\soffice.exe")

HTML = ROOT / "docs" / "paper.html"
DOCX = ROOT / "docs" / "paper-2col.docx"
PDF = ROOT / "docs" / "paper-2col-word.pdf"


def sh(cmd, env=None):
    print("+", " ".join(str(c) for c in cmd))
    subprocess.run([str(c) for c in cmd], cwd=str(ROOT), env=env, check=True)


def build_docx():
    import re
    env = {**os.environ, "NODE_PATH": str(SKILL / "node_modules")}
    # strip the on-page download bar so the badge links do not leak into the DOCX
    src = SCRATCH / "_paper_src.html"
    html = HTML.read_text(encoding="utf-8")
    html = re.sub(r'<div class="downloads">.*?</div>', "", html, flags=re.S, count=1)
    src.write_text(html, encoding="utf-8")
    mathml = SCRATCH / "_paper_mathml.html"
    conv = SCRATCH / "_paper_2col_conv.docx"
    sh(["node", SKILL / "scripts" / "katex_to_mathml.js",
        "--input", src, "--output", mathml], env=env)
    sh([PY, SKILL / "scripts" / "convert_to_docx.py",
        "--input", mathml, "--output", conv, "--profile", "two-column"])
    sh([PY, SKILL / "scripts" / "apply_academic_style.py",
        "--input", conv, "--output", DOCX, "--profile", "two-column",
        "--font-family", "Georgia",
        "--max-span-height-frac", "0.30", "--figure-max-height-in", "3.2"])
    print(f"wrote {DOCX} ({DOCX.stat().st_size:,} B)")


def render_pdf():
    # LibreOffice names output <stem>.pdf; convert in SCRATCH so it never collides
    # with the LaTeX docs/paper-2col.pdf, then move to the -word.pdf target.
    out = SCRATCH / f"{DOCX.stem}.pdf"
    if out.exists():
        out.unlink()
    sh([SOFFICE, "--headless", "--convert-to", "pdf", "--outdir",
        str(SCRATCH), str(DOCX)])
    if PDF.exists():
        PDF.unlink()
    shutil.move(str(out), str(PDF))
    print(f"wrote {PDF} ({PDF.stat().st_size:,} B)")


def main():
    build_docx()
    render_pdf()


if __name__ == "__main__":
    main()
