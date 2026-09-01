"""Build a professional two-column LaTeX PDF of the paper from docs/paper.html.

Pipeline:
  1. Strip figures from the HTML and let pandoc convert the prose to LaTeX
     (pandoc handles all escaping and inline formatting).
  2. Render each figure SVG to a vector PDF via Chromium (Playwright); copy the
     one raster figure (the atlas) as PNG.
  3. Replace pandoc's longtables (incompatible with twocolumn) with hand-authored
     booktabs tables, and its figure placeholders with real graphics floats.
  4. Wrap the transformed body in a journal-grade twocolumn preamble (newtx,
     microtype, booktabs, spanning floats) and compile with pdflatex.

Output: docs/paper-2col.pdf. Run after build_paper.py.
Requires: pandoc, Playwright (chromium), and a LaTeX engine (MiKTeX) on PATH.
"""
import base64
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HTML = ROOT / "docs" / "paper.html"
LATEX = ROOT / "latex"
FIG = LATEX / "fig"
TEX = LATEX / "paper2col.tex"
OUT_PDF = ROOT / "docs" / "paper-2col.pdf"

TITLE = ("Image Bundling Revisited: Codec-Specific Savings and a Measured "
         "Atlas Selector for Small Web Images")

# ----------------------------------------------------------------------------
# 1. figures: extract SVGs from the HTML, render to vector PDF; copy the raster
# ----------------------------------------------------------------------------

def extract_and_render_figures():
    FIG.mkdir(parents=True, exist_ok=True)
    html = HTML.read_text(encoding="utf-8")
    blocks = re.findall(r"<figure\b.*?</figure>", html, re.S)
    svg_targets = []
    for b in blocks:
        n = re.search(r"Figure\s+(\d+)", b).group(1)
        m_png = re.search(r"<img src='(img/[^']+)'", b) or re.search(r'<img src="(img/[^"]+)"', b)
        m_b64 = re.search(r'src="data:image/svg\+xml;base64,([^"]+)"', b)
        m_inl = re.search(r"(<svg\b.*?</svg>)", b, re.S)
        if m_png:
            shutil.copy(ROOT / "docs" / m_png.group(1), FIG / f"fig{n}.png")
        elif m_b64 or m_inl:
            svg = (base64.b64decode(m_b64.group(1)).decode("utf-8", "replace")
                   if m_b64 else m_inl.group(1))
            if "xmlns" not in svg[:80]:
                svg = svg.replace("<svg", "<svg xmlns='http://www.w3.org/2000/svg'", 1)
            p = FIG / f"fig{n}.svg"
            p.write_text(svg, encoding="utf-8")
            svg_targets.append(p)
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        pg = b.new_page()
        for s in svg_targets:
            svg = s.read_text(encoding="utf-8")
            m = re.search(r'viewbox="0 0 ([\d.]+) ([\d.]+)"', svg, re.I)
            w, h = (float(m.group(1)), float(m.group(2))) if m else (600, 400)
            page = (f'<!doctype html><html><head><style>*{{margin:0;padding:0}}'
                    f'html,body{{width:{w}px;height:{h}px}}svg{{display:block}}</style>'
                    f'</head><body>{svg}</body></html>')
            pg.set_content(page, wait_until="networkidle")
            pg.pdf(path=str(s.with_suffix(".pdf")), width=f"{w/96}in", height=f"{h/96}in",
                   margin={"top": "0", "bottom": "0", "left": "0", "right": "0"},
                   print_background=True)
        b.close()
    print("figures rendered")


# ----------------------------------------------------------------------------
# 2. prose: HTML (figures stripped) -> LaTeX via pandoc
# ----------------------------------------------------------------------------

def pandoc_body():
    html = HTML.read_text(encoding="utf-8")
    html = re.sub(r"<svg.*?</svg>", "[[SVGFIG]]", html, flags=re.S)
    html = re.sub(r'src="data:image/[^"]*"', 'src="[[DATAURI]]"', html)
    clean = LATEX / "_clean.html"
    clean.write_text(html, encoding="utf-8")
    body = LATEX / "_body.tex"
    subprocess.run(["pandoc", str(clean), "-f", "html", "-t", "latex", "-o", str(body)],
                   check=True)
    return body.read_text(encoding="utf-8")


# ----------------------------------------------------------------------------
# 3. hand-authored tables (booktabs). Negatives are colored via \ng.
# ----------------------------------------------------------------------------

def _num(v, dec=1):
    if isinstance(v, str):
        return v
    s = f"{v:.{dec}f}"
    return f"\\nv{{{s}}}" if v < 0 else s

def _comma(v):
    return f"{v:,}"

def t_row(cells):
    return " & ".join(cells) + r" \\"

def table1(cap):
    rows = [
        ("flat art 72px", 10, 19.4, "n/a", 4.3, -0.2),
        ("flat art 72px", 50, 26.3, 8.3, 5.4, 5.4),
        ("flat art 72px", 200, 25.1, 15.2, -3.1, -4.7),
        ("flat art 72px", 500, 26.3, 8.2, -5.7, -3.6),
        ("photos 56px", 10, 22.3, 15.3, -1.4, 2.9),
        ("photos 56px", 50, 27.7, 14.2, 1.1, 2.5),
        ("photos 56px", 200, 29.3, 18.8, 0.4, 3.7),
        ("photos 56px", 500, 29.8, 15.3, 0.8, 4.9),
        ("photos 112px", 10, 6.3, 2.7, -3.8, 1.8),
        ("photos 112px", 50, 8.4, 1.7, -0.9, 4.3),
        ("photos 112px", 200, 9.4, -0.1, -1.8, 4.3),
        ("photos 112px", 500, 9.8, -1.4, -1.6, 1.4),
        ("photos 224px", 10, 1.0, -4.3, -5.7, -3.4),
        ("photos 224px", 50, 1.8, -5.1, -2.8, 3.0),
        ("photos 224px", 200, 2.6, -8.2, -3.8, 0.3),
        ("photos 224px", 500, 3.0, -8.5, -3.6, -4.9),
    ]
    body = "\n".join(t_row([c[0], str(c[1])] + [_num(x) for x in c[2:]]) for c in rows)
    return float_table(1, cap, "col", r"@{}lr rrrr@{}",
                       r"class & N & JPEG & WebP & PNG & WebP-ll \\", body)

def table2(cap):
    rows = [
        ("flat art 72px, WebP", 0.991, 0.984, 0.954, 0.984, 0.960, 0.853),
        ("flat art 72px, JPEG", 0.979, 0.967, 0.946, 0.979, 0.967, 0.957),
        ("photos 56px, WebP", 0.979, 0.961, 0.925, 0.980, 0.963, 0.918),
        ("photos 224px, WebP", 0.978, 0.965, 0.942, 0.975, 0.960, 0.926),
    ]
    body = "\n".join(t_row([c[0]] + [f"{x:.3f}" for x in c[1:]]) for c in rows)
    head = (r"condition & \multicolumn{3}{c}{individual} & "
            r"\multicolumn{3}{c}{atlas} \\ \cmidrule(l){2-4}\cmidrule(l){5-7}" "\n"
            r"& mean & p5 & min & mean & p5 & min \\")
    return float_table(2, cap, "full", r"@{}l rrr rrr@{}", head, body)

def table3(cap):
    rows = [
        ("photos 56px", 42.2, 33.4, 2.8, 11.9),
        ("photos 112px", 17.1, 12.5, -21.8, -24.3),
        ("photos 224px", 4.0, 3.0, -28.2, -29.4),
    ]
    body = "\n".join(t_row([c[0]] + [_num(x) for x in c[1:]]) for c in rows)
    head = (r"class & \multicolumn{2}{c}{JPEG} & \multicolumn{2}{c}{WebP} \\"
            r" \cmidrule(l){2-3}\cmidrule(l){4-5}" "\n"
            r"& @60 & @70 & @60 & @70 \\")
    return float_table(3, cap, "col", r"@{}l rr rr@{}", head, body)

def _cell4(main, rng):
    m = f"\\nv{{{main}}}" if main.startswith("-") else main
    return f"\\makecell{{{m}\\\\ \\rng{{{rng}}}}}"

def table4(cap):
    rows = [
        ("photos 56px", ("+26.3", "[+25,+27]"), ("+19.2", "[+12,+21]"), ("+32.6", "[+31,+35]")),
        ("photos 112px", ("+8.4", "[+8,+9]"), ("+1.6", "[+1,+4]"), ("+12.4", "[+11,+13]")),
        ("photos 224px", ("+2.3", "[+2,+3]"), ("-7.0", "[-8,-5]"), ("+5.1", "[+4,+5]")),
    ]
    body = "\n".join(t_row([c[0]] + [_cell4(*c[i]) for i in (1, 2, 3)]) for c in rows)
    return float_table(4, cap, "col", r"@{}l ccc@{}",
                       r"class & JPEG & WebP & AVIF \\", body)

def table5(cap):
    rows = [
        ("individual WebP-lossless files (baseline)", 17328, 23536, 17050, 23007),
        ("WebP-lossless strip", 6966, 13580, 5422, 10606),
        ("PNG shared-palette strip", 10900, 23089, 6750, 14855),
        ("PNG strip (RGBA)", 18636, 38598, 17802, 37906),
        ("WebP-lossless grid", 7780, 15290, 7618, 14910),
        ("JPEG atlas (matched SSIM 0.97)", 53266, 122387, 51953, 117377),
    ]
    body = "\n".join(t_row([c[0]] + [_comma(x) for x in c[1:]]) for c in rows)
    head = (r"bundle & \multicolumn{2}{c}{clean corpus} & "
            r"\multicolumn{2}{c}{20\% duplicate} \\ \cmidrule(l){2-3}\cmidrule(l){4-5}" "\n"
            r"& 24px & 48px & 24px & 48px \\")
    return float_table(5, cap, "full", r"@{}l rrrr@{}", head, body)

def table6(cap):
    rows = [
        ("flat art", "localhost", "1.1", 565, 126, 128, 301, "4.5", "[3.9,5.4]", "1.9"),
        ("", "localhost", "2", 448, 126, 129, 319, "3.5", "[2.3,3.9]", "1.4"),
        ("", "localhost", "3", 597, 120, 135, 294, "5.0", "[4.5,5.7]", "2.0"),
        ("", "100 Mbit / 20 ms", "1.1", 2074, 241, 254, 466, "8.6", "[8.5,8.9]", "4.4"),
        ("", "100 Mbit / 20 ms", "2", 469, 213, 216, 467, "2.2", "[2.0,2.3]", "1.0"),
        ("", "100 Mbit / 20 ms", "3", 1579, 205, 198, 431, "7.7", "[7.0,8.1]", "3.7"),
        ("", "9 Mbit / 60 ms", "1.1", 5624, 790, 790, 997, "7.1", "[7.1,7.2]", "5.6"),
        ("", "9 Mbit / 60 ms", "2", 790, 730, 713, 1039, "1.1", "[1.1,1.1]", "0.8"),
        ("", "9 Mbit / 60 ms", "3", 4020, 708, 710, 1022, "5.7", "[5.5,5.8]", "3.9"),
        ("", "9 Mbit / 60 ms / 1\\% loss", "1.1", 5827, 829, 822, 1105, "7.0", "[6.2,7.5]", "5.3"),
        ("", "9 Mbit / 60 ms / 1\\% loss", "2", 878, 832, 720, 1098, "1.1", "[0.7,1.8]", "0.8"),
        ("", "9 Mbit / 60 ms / 1\\% loss", "3", 4149, 867, 871, 1189, "4.8", "[4.7,5.0]", "3.5"),
        ("photos", "localhost", "1.1", 758, 424, 400, 633, "1.8", "[1.5,1.9]", "1.2"),
        ("", "localhost", "2", 665, 419, 422, 632, "1.6", "[1.5,1.6]", "1.1"),
        ("", "localhost", "3", 835, 415, 425, 662, "2.0", "[1.7,2.3]", "1.3"),
        ("", "100 Mbit / 20 ms", "1.1", 2019, 780, 669, 1036, "2.6", "[2.6,2.6]", "1.9"),
        ("", "100 Mbit / 20 ms", "2", 692, 758, 709, 1038, "0.9", "[0.9,0.9]", "0.7"),
        ("", "100 Mbit / 20 ms", "3", 2075, 746, 763, 1002, "2.8", "[2.7,2.8]", "2.1"),
        ("", "9 Mbit / 60 ms", "1.1", 6199, 3824, 3897, 4246, "1.6", "[1.6,1.6]", "1.5"),
        ("", "9 Mbit / 60 ms", "2", 3743, 3771, 3866, 4294, "1.0", "[1.0,1.0]", "0.9"),
        ("", "9 Mbit / 60 ms", "3", 6218, 3902, 4021, 4427, "1.6", "[1.6,1.6]", "1.4"),
        ("", "9 Mbit / 60 ms / 1\\% loss", "1.1", 6933, 4612, 4490, 7890, "1.5", "[1.0,1.7]", "0.9"),
        ("", "9 Mbit / 60 ms / 1\\% loss", "2", 5576, 5993, 7226, 6476, "0.9", "[0.6,1.3]", "0.9"),
        ("", "9 Mbit / 60 ms / 1\\% loss", "3", 8793, 8404, 6875, 7934, "1.0", "[0.9,1.3]", "1.1"),
    ]
    out = []
    for i, c in enumerate(rows):
        atlx = f"\\textbf{{{c[7]}$\\times$}}~\\rng{{{c[8]}}}"
        cells = [c[0], c[1], c[2], _comma(c[3]), _comma(c[4]), _comma(c[5]), _comma(c[6]),
                 atlx, f"{c[9]}$\\times$"]
        line = t_row(cells)
        if c[0] == "photos" and i == 12:
            line = r"\midrule" + "\n" + line
        out.append(line)
    body = "\n".join(out)
    head = (r"class & network & \textsc{http} & indiv. & atlas & atlas$\times$4 & "
            r"byte-bundle & atlas speedup & bun. \\")
    return float_table(6, cap, "full", r"@{}ll c rrrr r r@{}", head, body)

def table7(cap):
    rows = [(50, 164, 89, 36, 81, 44, 87),
            (200, 379, 127, 23, 92, 139, 119),
            (500, 767, 129, 33, 106, 313, 143)]
    body = "\n".join(t_row([str(c[0])] + [str(x) for x in c[1:]]) for c in rows)
    head = (r"N & \multicolumn{2}{c}{individual} & \multicolumn{2}{c}{atlas} & "
            r"\multicolumn{2}{c}{byte-bundle} \\ "
            r"\cmidrule(l){2-3}\cmidrule(l){4-5}\cmidrule(l){6-7}" "\n"
            r"& ms & MB & ms & MB & ms & MB \\")
    return float_table(7, cap, "col", r"@{}r rr rr rr@{}", head, body)

def table8(cap):
    rows = [
        ("size + codec + one encode (baseline)", "4.95", "0.86"),
        (r"\quad + six source-image features", "6.05", "0.84"),
        ("10-tile probe encode", "2.31", "0.98"),
        ("20-tile probe encode", r"\textbf{1.62}", r"\textbf{0.98}"),
    ]
    body = "\n".join(t_row(list(c)) for c in rows)
    return float_table(8, cap, "col", r"@{}l rr@{}",
                       r"predictor & MAE (pp) & rank \\", body)

def table9(cap):
    rows = [
        ("noto", "flat-art", "byte-bundle (webp-ll)", "0.0", "+14.3", "0.0", "+5.1"),
        ("openmoji", "flat-art", "strip-atlas (webp-ll)", "0.0", "+3.7", "+6.4", "0.0"),
        ("flags", "flat-limited", "pixel-atlas (webp)", "0.0", "0.0", "+2.3", "+281.2"),
        ("flickr", "photo", "byte-bundle (webp)", "0.0", "+6.8", "0.0", "+643.0"),
        ("robo", "avatar", "strip-atlas (webp-ll)", "0.0", "+4.5", "+38.1", "0.0"),
    ]
    body = "\n".join(t_row([c[0], c[1], c[2]] + [f"{x}\\%" for x in c[3:]]) for c in rows)
    body += "\n\\midrule\n" + t_row([r"\textit{mean regret}", "", "",
                                     r"\textbf{0.0\%}", r"\textbf{+5.8\%}",
                                     r"\textbf{+9.4\%}", r"\textbf{+185.9\%}"])
    head = (r"corpus & class & heuristic choice & heur. & "
            r"always atlas & always bundle & always strip \\")
    return float_table(9, cap, "full", r"@{}lll rrrr@{}", head, body)

def table10(cap):
    rows = [
        (r"CSS \texttt{background-\allowbreak position}", "no", "via ARIA", "manual",
         "CSS only", "universal", "decorative icons"),
        (r"cropped \texttt{<img>} wrapper", "yes", "yes", "native", "CSS only",
         "broad", "semantic images"),
        (r"\texttt{object-\allowbreak view-\allowbreak box}", "yes", "yes", "native",
         "CSS only", "Chromium only", "native crop (emerging)"),
        ("byte-bundle + blob URLs", "yes (after JS)", "yes", "app-controlled",
         "JS + CSP", "broad APIs", "heterogeneous photos"),
    ]
    body = "\n".join(t_row(list(c)) for c in rows)
    head = (r"mechanism & native \texttt{<img>} & alt text & lazy / priority & "
            r"JS / CSP & support & best use \\")
    cols = (r"@{}>{\raggedright\arraybackslash}p{2.4cm} "
            r">{\raggedright\arraybackslash}p{1.6cm} l l l l "
            r">{\raggedright\arraybackslash}p{2.3cm}@{}")
    return float_table(10, cap, "full", cols, head, body)


def float_table(n, cap, width, colspec, head, body):
    env = "table*" if width == "full" else "table"
    size = r"\footnotesize" if width == "full" else r"\small"
    return (
        f"\\begin{{{env}}}[t]\n\\centering\n{size}\n"
        f"\\setlength{{\\tabcolsep}}{{4pt}}\n"
        f"\\begin{{tabular}}{{{colspec}}}\n\\toprule\n{head}\n\\midrule\n{body}\n"
        f"\\bottomrule\n\\end{{tabular}}\n"
        f"\\caption{{{cap}}}\n\\label{{tab:{n}}}\n\\end{{{env}}}\n")


# Keyed by FINAL document-order number (five sections in the appendix). Body:
# 1-5 (5.1/5.3), 6 predictor, 7 oracle. Appendix: 8 network, 9 memory, 10 rendering.
# table6()=network, table7()=memory, table8()=predictor, table9()=oracle.
TABLES = {1: table1, 2: table2, 3: table3, 4: table4, 5: table5,
          6: table8, 7: table9, 8: table6, 9: table7, 10: table10}

# figure placement: file (ext), width mode
# Final order: 1 atlas, 2 crossover, 3 flowchart (heuristic, wide), 4 network
# (appendix), 5 delta (appendix). extract_and_render_figures names files by caption.
FIGURES = {
    1: ("fig1.png", "col", 0.82),
    2: ("fig2.pdf", "col", 1.0),
    3: ("fig3.pdf", "full", 0.62),
    4: ("fig4.pdf", "col", 1.0),
    5: ("fig5.pdf", "col", 1.0),
}

def float_figure(n, cap):
    fname, width, scale = FIGURES[n]
    env = "figure*" if width == "full" else "figure"
    ref = r"\textwidth" if width == "full" else r"\columnwidth"
    return (f"\\begin{{{env}}}[t]\n\\centering\n"
            f"\\includegraphics[width={scale}{ref}]{{fig/{fname}}}\n"
            f"\\caption{{{cap}}}\n\\label{{fig:{n}}}\n\\end{{{env}}}\n")


# ----------------------------------------------------------------------------
# 4. caption extraction (strip the "\textbf{Kind N.} " prefix pandoc emitted)
# ----------------------------------------------------------------------------

def brace_match(s, start):
    """start is index of '{'; return (content, index_after_close)."""
    depth = 0
    for i in range(start, len(s)):
        if s[i] == "{":
            depth += 1
        elif s[i] == "}":
            depth -= 1
            if depth == 0:
                return s[start + 1:i], i + 1
    raise ValueError("unbalanced braces")

def caption_of(block):
    m = re.search(r"\\caption\{", block)
    content, _ = brace_match(block, m.end() - 1)
    content = re.sub(r"^\\textbf\{(Figure|Table) \d+\.\}\s*", "", content).strip()
    return content


# ----------------------------------------------------------------------------
# 5. assemble
# ----------------------------------------------------------------------------

# Elsevier journal class (the SPE / JSS submission look). [3p,twocolumn] is the
# final two-column journal layout. Follows the TwoColPaper/html2tex elsarticle
# template: scalable newtx (microtype needs scalable fonts), newtxmath after
# amssymb, rigid parskip + \flushbottom, tightened heading skips.
PREAMBLE = r"""\documentclass[3p,twocolumn]{elsarticle}
\usepackage[T1]{fontenc}
\usepackage[utf8]{inputenc}
\usepackage{newtxtext}
\usepackage{amsmath}
\let\Bbbk\relax
\usepackage{newtxmath}
\usepackage{microtype}
\usepackage{graphicx}
\usepackage{booktabs}
\usepackage{array}
\usepackage{makecell}
\usepackage[table,dvipsnames]{xcolor}
\usepackage{caption}
\usepackage{fancyvrb}
\usepackage{hyperref}

\DeclareUnicodeCharacter{2212}{\ensuremath{-}}
\DeclareUnicodeCharacter{00D7}{\ensuremath{\times}}
\DeclareUnicodeCharacter{03A3}{\ensuremath{\Sigma}}
\DeclareUnicodeCharacter{03A0}{\ensuremath{\Pi}}
\DeclareUnicodeCharacter{03B8}{\ensuremath{\theta}}
\DeclareUnicodeCharacter{2208}{\ensuremath{\in}}
\DeclareUnicodeCharacter{2265}{\ensuremath{\geq}}
\DeclareUnicodeCharacter{2264}{\ensuremath{\leq}}
\DeclareUnicodeCharacter{2192}{\ensuremath{\rightarrow}}
\DeclareUnicodeCharacter{2248}{\ensuremath{\approx}}
\DeclareUnicodeCharacter{2009}{\,}
\DeclareUnicodeCharacter{00B7}{\textperiodcentered}

\definecolor{negred}{RGB}{192,57,43}
\definecolor{greyx}{RGB}{130,135,143}
\definecolor{linkblue}{RGB}{30,80,140}
\newcommand{\nv}[1]{\textcolor{negred}{#1}}
\newcommand{\rng}[1]{{\scriptsize\color{greyx}#1}}
\hypersetup{colorlinks=true,allcolors=linkblue,urlcolor=linkblue,breaklinks=true}

% Auto-numbered captions (this build emits floats in document order, so
% LaTeX numbering agrees with the prose references to "Table N" / "Figure N").
\captionsetup{font=small,labelfont=bf,labelsep=period,skip=5pt}
\captionsetup[table]{position=below}

\flushbottom
\setlength{\parskip}{0pt}
\AtBeginDocument{\setlength{\parskip}{0pt}}
\makeatletter
\renewcommand\section{\@startsection{section}{1}{\z@}%
           {12\p@ \@plus 3\p@ \@minus 4\p@}%
           {6\p@ \@plus 2\p@ \@minus 2\p@}%
           {\normalsize\bfseries\boldmath}}
\renewcommand\subsection{\@startsection{subsection}{2}{\z@}%
           {10\p@ \@plus 3\p@ \@minus 3\p@}%
           {3\p@ \@plus 2\p@ \@minus 1\p@}%
           {\normalfont\normalsize\itshape}}
\makeatother
\setlength{\intextsep}{6pt plus 1pt minus 3pt}
\setlength{\textfloatsep}{8pt plus 1pt minus 3pt}
\setlength{\floatsep}{8pt plus 1pt minus 3pt}
\setlength{\emergencystretch}{2em}

\renewcommand{\UrlFont}{\small\ttfamily}
\DefineVerbatimEnvironment{code}{Verbatim}{fontsize=\footnotesize,frame=leftline,
  framerule=0.4pt,rulecolor=\color{greyx},xleftmargin=6pt,samepage=true}

\newcommand{\reference}[1]{\par\noindent\hangindent=1.4em\hangafter=1 #1\par\vspace{2pt}}

\journal{Software: Practice and Experience}
"""

FRONTMATTER = r"""\begin{frontmatter}
\title{\vspace*{-1.5\baselineskip}__TITLE__}
\author[hit]{Alexander Apartsin\corref{cor1}}
\ead{apartsin@gmail.com}
\author[afeka]{Yehudit Aperstein}
\cortext[cor1]{Corresponding author}
\address[hit]{School of Computer Science, Faculty of Sciences, Holon Institute of Technology (HIT), Holon, Israel}
\address[afeka]{Intelligent Systems, Afeka Academic College of Engineering, Tel-Aviv, Israel}
\begin{abstract}
__ABS1__

__ABS2__
\end{abstract}
\end{frontmatter}
"""


def build():
    extract_and_render_figures()
    raw = pandoc_body()

    # isolate the body (Introduction .. References) and the appendix (after refs)
    start = raw.index(r"\subsection{1")
    end = raw.index(r"\subsection{References}")
    prose = raw[start:end]
    appendix = raw[raw.index(r"\subsection{Appendix A}"):]

    # abstract paragraphs (between the venue line and the Introduction heading)
    ap = re.search(r"\nAbstract\n\n(.*?)\n\n(.*?)\n\n\\subsection\{1", raw, re.S)
    abs1, abs2 = ap.group(1).strip(), ap.group(2).strip()

    # replace figure / longtable blocks with hand-authored floats (keyed by the
    # caption's final number, which TABLES/FIGURES map to the right content)
    def repl(m):
        block = m.group(0)
        km = re.search(r"\\textbf\{(Figure|Table) (\d+)\.\}", block)
        kind, num = km.group(1), int(km.group(2))
        cap = caption_of(block)
        return float_figure(num, cap) if kind == "Figure" else TABLES[num](cap)

    def floats(text):
        text = re.sub(r"\\begin\{figure\}.*?\\end\{figure\}", repl, text, flags=re.S)
        text = re.sub(r"\\begin\{longtable\}.*?\\end\{longtable\}", repl, text, flags=re.S)
        # drop pandoc's duplicated standalone "\textbf{Table N.} ..." caption paragraph
        return re.sub(r"\n\\textbf\{Table \d+\.\}.*?(?=\n\n)", "", text, flags=re.S)

    prose, appendix = floats(prose), floats(appendix)

    # body headings: drop manual numbers, promote levels to real sectioning
    prose = re.sub(r"\\subsubsection\{[\d.]+~~(.*?)\}(\\label\{[^}]*\})?",
                   r"\\subsection{\1}", prose, flags=re.S)
    prose = re.sub(r"\\subsection\{[\d.]+~~(.*?)\}(\\label\{[^}]*\})?",
                   r"\\section{\1}", prose, flags=re.S)

    # appendix: unnumbered "Appendix A" head + A.n run-in subsections; strip the
    # trailing author/footer line pandoc appends after the last appendix block
    appendix = appendix.replace(r"\subsection{Appendix A}", r"\section*{Appendix A}")
    appendix = re.sub(r"\\subsubsection\{(A\.\d+)~~(.*?)\}(\\label\{[^}]*\})?",
                      r"\\subsection*{\1\\quad \2}", appendix, flags=re.S)
    appendix = re.sub(r"\n\nAlexander Apartsin[^\n]*\n?", "\n", appendix)

    prose = re.sub(r"\\label\{[^}]*\}", "", prose)
    appendix = re.sub(r"\\label\{[^}]*\}", "", appendix)

    # code blocks: verbatim -> our styled 'code' env
    def code_env(s):
        return s.replace(r"\begin{verbatim}", r"\begin{code}").replace(
            r"\end{verbatim}", r"\end{code}")
    prose, appendix = code_env(prose), code_env(appendix)

    # typographic cleanups. pandoc emits possessives as "\textquotesingle{}" (a
    # real space follows) or "\textquotesingle " (the space is only the control-word
    # terminator and must be dropped so "group' s" becomes "group's").
    def fix_quotes(s):
        s = s.replace(r"\textquotesingle{}", "'")
        s = re.sub(r"\\textquotesingle\s", "'", s)
        return s.replace(r"{[}", "[").replace(r"{]}", "]")
    prose, appendix, abs1, abs2 = (fix_quotes(prose), fix_quotes(appendix),
                                   fix_quotes(abs1), fix_quotes(abs2))

    references = build_references()

    doc = (PREAMBLE
           + "\n\\begin{document}\n"
           + FRONTMATTER.replace("__TITLE__", TITLE).replace("__ABS1__", abs1)
                        .replace("__ABS2__", abs2)
           + prose
           + "\n\\section*{References}\n{\\small\n" + references + "\n}\n"
           + appendix
           + "\n\\end{document}\n")
    TEX.write_text(doc, encoding="utf-8")
    print(f"wrote {TEX}")


def build_references():
    md = (ROOT / "scripts").parent  # placeholder; refs are hardcoded below
    return format_refs(REFS)


def _esc(s):
    for a, b in [("\\", r"\textbackslash{}"), ("&", r"\&"), ("%", r"\%"),
                 ("$", r"\$"), ("#", r"\#"), ("_", r"\_"), ("{", r"\{"),
                 ("}", r"\}"), ("~", r"\textasciitilde{}"), ("^", r"\textasciicircum{}")]:
        s = s.replace(a, b)
    return s

def format_refs(refs):
    out = []
    for r in refs:
        # protect URLs and DOIs, escape the rest, restore as \url
        toks = []
        def sub(m):
            toks.append(m.group(0)); return f"\0{len(toks)-1}\0"
        tmp = re.sub(r"https?://\S+", sub, r)
        tmp = re.sub(r"doi:(\S+)", lambda m: sub_doi(m, toks), tmp)
        tmp = _esc(tmp)
        def restore(m):
            t = toks[int(m.group(1))]
            if t.startswith("doi:"):
                return r"\url{https://doi.org/" + t[4:] + "}"
            return r"\url{" + t + "}"
        tmp = re.sub(r"\x00(\d+)\x00", restore, tmp)
        out.append(f"\\reference{{{tmp}}}")
    return "\n".join(out)

def sub_doi(m, toks):
    toks.append(m.group(0)); return f"\0{len(toks)-1}\0"


REFS = [
    "[1] C. Johnson. Forgo JS packaging? Not so fast. Khan Academy Engineering, 2015. https://blog.khanacademy.org/forgo-js-packaging-not-so-fast/",
    "[2] C. Coyier. Musings on HTTP/2 and bundling. CSS-Tricks. https://css-tricks.com/musings-on-http2-and-bundling/",
    "[3] M. Varvello, K. Schomp, D. Naylor, J. Blackburn, A. Finamore, K. Papagiannaki. Is the Web HTTP/2 Yet? Passive and Active Measurement (PAM), LNCS 9631, 2016. doi:10.1007/978-3-319-30505-9_17",
    "[4] R. Meireles, J. Liu, P. Steenkiste. A study of HTTP/2's Server Push Performance Potential. arXiv:2207.05885, 2022.",
    "[5] T. Hunter. HTTP/3 is fast. Request Metrics, 2022. https://requestmetrics.com/web-performance/http3-is-fast/",
    "[6] T. Eden. What's the smallest file size for a 1 pixel image? 2024. https://shkspr.mobi/blog/2024/01/whats-the-smallest-file-size-for-a-1-pixel-image/",
    "[7] J. Sneyers. One pixel is worth three thousand words. Cloudinary Blog. https://cloudinary.com/blog/one_pixel_is_worth_three_thousand_words",
    "[8] HTTP Archive. Web Almanac 2024, Media chapter. https://almanac.httparchive.org/en/2024/media",
    "[9] Unity Technologies. Sprites.AtlasSettings.paddingPower documentation. https://docs.unity3d.com/ScriptReference/Sprites.AtlasSettings-paddingPower.html",
    "[10] D. Shea. CSS Sprites: Image Slicing's Kiss of Death. A List Apart, 2004. https://alistapart.com/article/sprites/",
    "[11] Google. Web Fundamentals: HTTP/2 and resource bundling guidance. https://web.dev/articles/http2",
    "[12] M. Belshe, R. Peon, M. Thomson. Hypertext Transfer Protocol Version 2 (HTTP/2). RFC 7540, IETF, 2015. doi:10.17487/RFC7540",
    "[13] M. Bishop. HTTP/3. RFC 9114, IETF, 2022. doi:10.17487/RFC9114",
    "[14] J. Ruth, D. Kunze, O. Hohlfeld. Measuring HTTP/3: Adoption and Performance. arXiv:2102.12358, 2021.",
    "[15] U. Goel et al. Domain-Sharding for Faster HTTP/2 in Lossy Cellular Networks. arXiv:1707.05836, 2017.",
    "[16] Cloudinary. Image optimization documentation (format selection and the <5,000-pixel AVIF policy). https://cloudinary.com/documentation/image_optimization",
    "[17] ITU-T T.81 / ISO IEC 10918-1. Digital compression and coding of continuous-tone still images (JPEG), 1992.",
    "[18] W3C. Portable Network Graphics (PNG) Specification, 3rd ed., 2003. https://www.w3.org/TR/PNG/",
    "[19] Google. WebP Container and Bitstream Specification. https://developers.google.com/speed/webp/docs/riff_container",
    "[20] J. Ratcliff. Texture atlas / sprite packing techniques. Game Developer, 2002.",
    "[21] J. Jylanki. A Thousand Ways to Pack the Bin: rectangle bin-packing algorithms (skyline, MaxRects), 2010.",
    "[22] J. Alakuijala, Z. Szabadka. Brotli Compressed Data Format. RFC 7932, IETF, 2016. doi:10.17487/RFC7932",
    "[23] Y. Collet, M. Kucherawy. Zstandard Compression and the application/zstd Media Type. RFC 8878, IETF, 2021. doi:10.17487/RFC8878",
    "[24] P. Meenan, Y. Weiss. Compression Dictionary Transport. RFC 9842, IETF, 2025. doi:10.17487/RFC9842",
    "[25] Z. Wang, A. C. Bovik, H. R. Sheikh, E. P. Simoncelli. Image Quality Assessment: From Error Visibility to Structural Similarity. IEEE Trans. Image Processing 13(4):600-612, 2004. doi:10.1109/TIP.2003.819861",
    "[26] X. S. Wang, A. Balasubramanian, A. Krishnamurthy, D. Wetherall. Demystifying Page Load Performance with WProf. USENIX NSDI, 2013.",
    "[27] X. S. Wang, A. Balasubramanian, A. Krishnamurthy, D. Wetherall. How Speedy is SPDY? USENIX NSDI, 2014.",
    "[28] R. Netravali, A. Goyal, J. Mickens, H. Balakrishnan. Polaris: Faster Page Loads Using Fine-grained Dependency Tracking. USENIX NSDI, 2016.",
    "[29] R. Marx, T. Wijnants, P. Quax, A. Faes, W. Lamotte. Concatenation, Embedding and Sharding: Do HTTP/1 Performance Best Practices Make Sense in HTTP/2? WEBIST, 2017.",
    "[30] C. Sander, I. Kunze, K. Wehrle, J. Ruth. Sharding and HTTP/2 Connection Reuse Revisited: Why Are There Still Redundant Connections? ACM IMC, 2021. doi:10.1145/3487552.3487832",
    "[31] N. Barman, M. G. Martini. An Evaluation of the Next-Generation Image Coding Standard AVIF. IEEE QoMEX, 2020. doi:10.1109/QoMEX48832.2020.9123131",
    "[32] B. Levy, S. Petitjean, N. Ray, J. Maillot. Least Squares Conformal Maps for Automatic Texture Atlas Generation. ACM SIGGRAPH / ACM TOG 21(3), 2002. doi:10.1145/566654.566590",
    "[33] J. Marszalkowski, J. Mizgajski, D. Mokwa, M. Drozdowski. Analysis and Solution of CSS-Sprite Packing Problem. ACM Trans. Web 10(1), Article 1, 2016. doi:10.1145/2818377",
    "[34] M. Butkiewicz, H. V. Madhyastha, V. Sekar. Understanding Website Complexity: Measurements, Metrics, and Implications. ACM Internet Measurement Conference (IMC), 2011. doi:10.1145/2068816.2068846",
    "[35] S. Souders. High Performance Web Sites: Essential Knowledge for Front-End Engineers. O'Reilly Media, 2007. ISBN 978-0-596-52930-7.",
    "[36] H. de Saxce, I. Oprescu, Y. Chen. Is HTTP/2 really faster than HTTP/1.1? IEEE INFOCOM Workshops (INFOCOM WKSHPS), 2015, pp. 293-299. doi:10.1109/INFCOMW.2015.7179400",
    "[37] A. M. Kakhki, S. Jero, D. Choffnes, C. Nita-Rotaru, A. Mislove. Taking a Long Look at QUIC: An Approach for Rigorous Evaluation of Rapidly Evolving Transport Protocols. ACM Internet Measurement Conference (IMC), 2017, pp. 290-303. doi:10.1145/3131365.3131368",
    "[38] J. Alakuijala, R. van Asseldonk, S. Boukortt, M. Bruse, I.-M. Comsa, M. Firsching, et al. JPEG XL next-generation image compression architecture and coding tools. Proc. SPIE 11137, Applications of Digital Image Processing XLII, 111370K, 2019. doi:10.1117/12.2529237",
    "[39] Google. WebP Compression Study, 2011. https://developers.google.com/speed/webp/docs/webp_study",
    "[40] G. Randers-Pehrson. MNG (Multiple-image Network Graphics) Format, Version 1.0, 2001. http://www.libpng.org/pub/mng/spec/ (APNG is standardized in the W3C PNG Specification, 3rd ed. [18]).",
    "[41] ISO/IEC 23008-12:2017. Information technology: High efficiency coding and media delivery in heterogeneous environments, Part 12: Image File Format (HEIF).",
    "[42] J. Mogul, B. Krishnamurthy, F. Douglis, A. Feldmann, Y. Goland, A. van Hoff, D. Hellerstein. Delta Encoding in HTTP. RFC 3229, IETF, 2002. doi:10.17487/RFC3229",
    "[43] D. Korn, J. MacDonald, J. Mogul, K. Vo. The VCDIFF Generic Differencing and Compression Data Format. RFC 3284, IETF, 2002. doi:10.17487/RFC3284",
    "[44] J. Butler, W.-H. Lee, B. McQuade, K. Mixter. A Proposal for Shared Dictionary Compression over HTTP (SDCH). IETF Internet-Draft draft-lee-sdch-spec, 2008.",
    "[45] R. Fielding, M. Nottingham, J. Reschke (Eds.). HTTP Caching. RFC 9111 (STD 98), IETF, 2022. doi:10.17487/RFC9111",
]


def compile_pdf():
    for _ in range(2):
        subprocess.run(["latexmk", "-pdf", "-interaction=nonstopmode", "paper2col.tex"],
                       cwd=str(LATEX), check=False,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    built = LATEX / "paper2col.pdf"
    if not built.exists():
        raise SystemExit("latex compile failed; see latex/paper2col.log")
    shutil.copy(built, OUT_PDF)
    print(f"wrote {OUT_PDF} ({OUT_PDF.stat().st_size:,} B)")


if __name__ == "__main__":
    build()
    compile_pdf()
