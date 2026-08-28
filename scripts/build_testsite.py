"""Build the Phase 2 test site: individual vs atlas vs chunked-atlas vs byte-bundle.

Assets are WebP q80 (in-scope codec). Every page defines window.__done, a Promise
resolving (after all tiles are decoded and two rAFs have painted) to
{allVisibleMs, resources:[...], nRendered}.

Conditions per (class, n): individual, atlas1, atlas4 (chunked), bundlebin
(concatenation of the individually-encoded files served as ONE .bin + offset index;
client slices and decodes each tile via blob URLs, keeping per-file codec adaptation).
"""
import io
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
WWW = ROOT / "www"
CLASSES = {"emoji": 72, "photos": 224}
COUNTS = [10, 50, 200, 500]
QUALITY = 80

HEAD = ("<!DOCTYPE html><html><head><meta charset='utf-8'>"
        "<script>performance.setResourceTimingBufferSize(4096)</script>")

COMMON_JS = """
<script>
window.__done = (async () => {
  await READY;
  await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
  const mark = performance.now();
  const resources = performance.getEntriesByType('resource')
    .filter(e => e.name.match(/\\.(webp|png|jpg|bin)$/))
    .map(e => ({name: e.name.split('/').pop(), transferSize: e.transferSize,
                encodedBodySize: e.encodedBodySize, protocol: e.nextHopProtocol,
                dur: e.duration}));
  return {allVisibleMs: mark, resources, nRendered: document.querySelectorAll('.tile').length};
})();
</script>
"""


def save_webp(arr, path):
    Image.fromarray(arr).save(path, "WEBP", quality=QUALITY, method=6)
    return path.stat().st_size


def load_tiles(cls, n):
    tiles = []
    for f in sorted((ROOT / "assets" / cls).iterdir())[:n]:
        im = Image.open(f)
        if im.mode in ("RGBA", "LA", "P"):
            im = im.convert("RGBA")
            im = Image.alpha_composite(Image.new("RGBA", im.size, (255,) * 4), im)
        tiles.append(np.asarray(im.convert("RGB")))
    return tiles


def build_atlas(tiles):
    n = len(tiles)
    th, tw, _ = tiles[0].shape
    cols = math.ceil(math.sqrt(n))
    rows = math.ceil(n / cols)
    atlas = np.full((rows * th, cols * tw, 3), 255, np.uint8)
    coords = []
    for i, t in enumerate(tiles):
        r, c = divmod(i, cols)
        atlas[r * th:(r + 1) * th, c * tw:(c + 1) * tw] = t
        coords.append((c * tw, r * th))
    return atlas, coords


def page(fname, body, ready_js, ts):
    html = (f"{HEAD}<style>body{{margin:0;display:flex;flex-wrap:wrap}}"
            f".tile{{width:{ts}px;height:{ts}px}}</style></head><body>"
            f"{body}<script>const READY = (async () => {{{ready_js}}})();</script>"
            f"{COMMON_JS}</body></html>")
    (WWW / fname).write_text(html, encoding="utf-8")


def main():
    WWW.mkdir(exist_ok=True)
    for old in WWW.glob("*.avif"):
        old.unlink()
    manifest = []
    for cls, ts in CLASSES.items():
        all_tiles = load_tiles(cls, max(COUNTS))
        for n in COUNTS:
            tiles = all_tiles[:n]
            # --- individual files (also the payload source for bundlebin)
            names, blobs, total = [], [], 0
            for i, t in enumerate(tiles):
                nm = f"{cls}_{n}_t{i:03d}.webp"
                b = io.BytesIO()
                Image.fromarray(t).save(b, "WEBP", quality=QUALITY, method=6)
                blob = b.getvalue()
                (WWW / nm).write_bytes(blob)
                blobs.append(blob)
                names.append(nm)
                total += len(blob)
            body = "".join(f"<img class='tile' src='{nm}'>" for nm in names)
            ready = ("await Promise.all([...document.images].map(i => i.decode()));")
            page(f"individual_{cls}_{n}.html", body, ready, ts)
            manifest.append({"cls": cls, "n": n, "cond": "individual",
                             "encoded_bytes": total, "files": n})
            # --- byte bundle: concat + offsets
            bin_name = f"bundle_{cls}_{n}.bin"
            offsets, off = [], 0
            with (WWW / bin_name).open("wb") as f:
                for blob in blobs:
                    f.write(blob)
                    offsets.append([off, len(blob)])
                    off += len(blob)
            ready = (
                f"const resp = await fetch('{bin_name}');"
                "const buf = await resp.arrayBuffer();"
                f"const offs = {json.dumps(offsets)};"
                "await Promise.all(offs.map(async ([o, l]) => {"
                "  const url = URL.createObjectURL("
                "    new Blob([buf.slice(o, o + l)], {type: 'image/webp'}));"
                "  const im = new Image(); im.className = 'tile'; im.src = url;"
                "  document.body.appendChild(im);"
                "  await im.decode();"
                "}));")
            page(f"bundlebin_{cls}_{n}.html", "", ready, ts)
            manifest.append({"cls": cls, "n": n, "cond": "bundlebin",
                             "encoded_bytes": off, "files": 1})
            # --- atlas1 and atlas4
            for chunks in (1, 4):
                if chunks == 4 and n < 40:
                    continue
                per = math.ceil(n / chunks)
                total, divs, urls = 0, [], []
                for c in range(chunks):
                    sub = tiles[c * per:(c + 1) * per]
                    if not sub:
                        continue
                    atlas, coords = build_atlas(sub)
                    nm = f"atlas_{cls}_{n}_c{chunks}_{c}.webp"
                    total += save_webp(atlas, WWW / nm)
                    urls.append(nm)
                    for (x, y) in coords:
                        divs.append(f"<div class='tile' style=\"background-image:url({nm});"
                                    f"background-position:-{x}px -{y}px\"></div>")
                ready = (f"await Promise.all({json.dumps(urls)}.map(u => {{"
                         "const im = new Image(); im.src = u; return im.decode();}));")
                page(f"atlas{chunks}_{cls}_{n}.html", "".join(divs), ready, ts)
                manifest.append({"cls": cls, "n": n, "cond": f"atlas{chunks}",
                                 "encoded_bytes": total, "files": chunks})
    json.dump(manifest, (WWW / "manifest.json").open("w"), indent=1)
    for m in manifest:
        print(m)


if __name__ == "__main__":
    main()
