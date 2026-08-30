"""Browser memory + user-visible timing (review items W5 / P1.7).

Measures, for N in {50,200,500} and three serving representations (individual WebP files,
one WebP pixel atlas, one self-describing byte-bundle), the user-visible load milestones
and the renderer memory the images actually cost in a real browser, rather than only the
analytical width x height x 4 bound. Memory is the renderer process-tree RSS delta over a
blank baseline (captures the C++-side decoded-image cache that JS-heap APIs miss;
measureUserAgentSpecificMemory is not exposed in this Chromium build). All three
representations render the same 96 px photographic tiles in the same grid.

Local, no network shaping: this isolates decode/paint/memory, not transport.
"""
import http.server
import io
import json
import socketserver
import threading
from pathlib import Path

import numpy as np
import psutil
from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "results" / "static" / "e_memory" / "site"
OUT = ROOT / "results" / "static" / "e_memory"
SITE.mkdir(parents=True, exist_ok=True)
NS = [50, 200, 500]
TILE = 96
COLS = 10          # fixed grid width; ~9 rows fit a 900px viewport
Q = 80


def build_site():
    files = sorted(p for p in (ROOT / "assets" / "photos").iterdir()
                   if p.suffix.lower() in (".jpg", ".jpeg", ".png"))[:max(NS)]
    tiles = [np.asarray(Image.open(f).convert("RGB").resize((TILE, TILE), Image.LANCZOS))
             for f in files]
    manifest = {}
    for n in NS:
        sub = tiles[:n]
        # individual files
        idir = SITE / f"ind_{n}"; idir.mkdir(exist_ok=True)
        for i, t in enumerate(sub):
            Image.fromarray(t).save(idir / f"{i}.webp", "WEBP", quality=Q, method=4)
        # atlas
        rows = (n + COLS - 1) // COLS
        atlas = np.full((rows * TILE, COLS * TILE, 3), 255, np.uint8)
        for i, t in enumerate(sub):
            r, c = divmod(i, COLS); atlas[r * TILE:(r + 1) * TILE, c * TILE:(c + 1) * TILE] = t
        Image.fromarray(atlas).save(SITE / f"atlas_{n}.webp", "WEBP", quality=Q, method=4)
        # self-describing byte-bundle
        offs, off, payloads = {}, 0, []
        for i, t in enumerate(sub):
            b = io.BytesIO(); Image.fromarray(t).save(b, "WEBP", quality=Q, method=4)
            blob = b.getvalue(); payloads.append(blob); offs[str(i)] = [off, len(blob)]
            off += len(blob)
        header = json.dumps(offs, separators=(",", ":")).encode()
        with (SITE / f"bundle_{n}.bin").open("wb") as f:
            f.write(len(header).to_bytes(4, "big")); f.write(header)
            for blob in payloads:
                f.write(blob)
        manifest[n] = {"rows": rows}
    (SITE / "manifest.json").write_text(json.dumps(manifest))
    return manifest


# --- HTML templates: each stamps window.__t = {firstTile, firstViewport, allVisible} ---
COMMON = """
<style>#g{{font-size:0}} .t{{display:inline-block;width:96px;height:96px}}</style>
<div id=g></div>
<script>
const N={n}, COLS={cols}, VIEW_ROWS=Math.ceil(900/96);
const viewCount=Math.min(N, COLS*VIEW_ROWS);
let loaded=0, firstTile=0, firstViewport=0, viewLoaded=0;
const t0=performance.now();
function tile(i){{ loaded++;
  if(!firstTile) firstTile=performance.now()-t0;
  if(i<viewCount){{ viewLoaded++; if(viewLoaded===viewCount) firstViewport=performance.now()-t0; }}
  if(loaded===N){{ requestAnimationFrame(()=>requestAnimationFrame(()=>{{
    window.__t={{firstTile:Math.round(firstTile),firstViewport:Math.round(firstViewport),
                 allVisible:Math.round(performance.now()-t0)}}; }})); }}
}}
</script>
"""

IND = COMMON + """
<script>
const g=document.getElementById('g');
for(let i=0;i<N;i++){{ const im=new Image(96,96); im.className='t';
  im.onload=()=>tile(i); im.src='ind_{n}/'+i+'.webp'; g.appendChild(im); }}
</script>"""

ATLAS = COMMON + """
<script>
const g=document.getElementById('g');
const a=new Image(); a.onload=()=>{{
  for(let i=0;i<N;i++){{ const r=Math.floor(i/COLS),c=i%COLS; const d=document.createElement('div');
    d.className='t'; d.style.background="url(atlas_{n}.webp) -"+(c*96)+"px -"+(r*96)+"px";
    g.appendChild(d); tile(i); }} }};
a.src='atlas_{n}.webp';
</script>"""

BUNDLE = COMMON + """
<script>
(async()=>{{ const g=document.getElementById('g');
  const buf=await fetch('bundle_{n}.bin').then(r=>r.arrayBuffer());
  const dv=new DataView(buf); const hlen=dv.getUint32(0);
  const offs=JSON.parse(new TextDecoder().decode(new Uint8Array(buf,4,hlen)));
  const base=4+hlen;
  for(let i=0;i<N;i++){{ const [o,l]=offs[i];
    const url=URL.createObjectURL(new Blob([buf.slice(base+o,base+o+l)],{{type:'image/webp'}}));
    const im=new Image(96,96); im.className='t'; im.onload=()=>tile(i); im.src=url; g.appendChild(im); }}
}})();
</script>"""


def write_pages():
    for n in NS:
        (SITE / f"ind_{n}.html").write_text(IND.format(n=n, cols=COLS))
        (SITE / f"atlas_{n}.html").write_text(ATLAS.format(n=n, cols=COLS))
        (SITE / f"bundle_{n}.html").write_text(BUNDLE.format(n=n, cols=COLS))


def serve():
    handler = http.server.SimpleHTTPRequestHandler
    class H(handler):
        def __init__(self, *a, **k): super().__init__(*a, directory=str(SITE), **k)
        def log_message(self, *a): pass
    srv = socketserver.ThreadingTCPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, srv.server_address[1]


def chrome_pids():
    s = set()
    for p in psutil.process_iter(["name"]):
        n = (p.info["name"] or "").lower()
        if "chrome" in n or "chromium" in n:
            s.add(p.pid)
    return s


def rss(pids):
    t = 0
    for pid in pids:
        try:
            t += psutil.Process(pid).memory_info().rss
        except Exception:
            pass
    return t


def main():
    build_site(); write_pages()
    srv, port = serve()
    rows = []
    with sync_playwright() as pw:
        for n in NS:
            for cond in ("ind", "atlas", "bundle"):
                before = chrome_pids()
                b = pw.chromium.launch()
                blank = b.new_page(); blank.goto("about:blank"); blank.wait_for_timeout(700)
                ours = chrome_pids() - before
                base = rss(ours)
                pg = b.new_page()
                pg.goto(f"http://127.0.0.1:{port}/{cond}_{n}.html", wait_until="commit")
                pg.wait_for_function("window.__t!==undefined", timeout=60000)
                t = pg.evaluate("window.__t")
                pg.wait_for_timeout(800)  # let decode settle
                ours = chrome_pids() - before
                mem = (rss(ours) - base) / 1e6
                b.close()
                row = {"n": n, "cond": cond, **t, "mem_mb": round(mem, 1)}
                rows.append(row)
                print(f"{cond:7} N={n:<3} firstTile={t['firstTile']:>5} "
                      f"firstViewport={t['firstViewport']:>5} allVisible={t['allVisible']:>5} ms  "
                      f"mem={mem:>6.1f} MB", flush=True)
                json.dump(rows, (OUT / "results.json").open("w"), indent=1)
    srv.shutdown()
    print("MEMORY DONE")


if __name__ == "__main__":
    main()
