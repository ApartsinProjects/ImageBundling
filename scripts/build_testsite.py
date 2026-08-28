"""Build the Phase 2 test site: individual vs atlas vs chunked-atlas pages.

Writes www/: encoded assets + one HTML page per condition. Every page defines
window.__done, a Promise resolving (after all tiles are decoded and two rAFs have
painted) to {allVisibleMs, resources:[{name, transferSize, protocol}], nRendered}.

Conditions per (class, n): individual, atlas1, atlas4 (chunked into 4).
Codec: AVIF q50 (Phase 1 winner, universally decodable in modern browsers).
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
QUALITY = 50

COMMON_JS = """
<script>
window.__done = (async () => {
  const t0 = performance.timeOrigin;
  await Promise.all(PRELOAD.map(u => {
    const im = new Image(); im.src = u;
    return im.decode();
  }));
  await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
  const mark = performance.now();
  const resources = performance.getEntriesByType('resource')
    .filter(e => e.name.match(/\\.(avif|webp|png|jpg)$/))
    .map(e => ({name: e.name.split('/').pop(), transferSize: e.transferSize,
                encodedBodySize: e.encodedBodySize, protocol: e.nextHopProtocol,
                dur: e.duration}));
  return {allVisibleMs: mark, resources, nRendered: document.querySelectorAll('.tile').length};
})();
</script>
"""


def load_tiles(cls, n):
    tiles = []
    for f in sorted((ROOT / "assets" / cls).iterdir())[:n]:
        im = Image.open(f)
        if im.mode in ("RGBA", "LA", "P"):
            im = im.convert("RGBA")
            im = Image.alpha_composite(Image.new("RGBA", im.size, (255,) * 4), im)
        tiles.append(np.asarray(im.convert("RGB")))
    return tiles


def save_avif(arr, path):
    Image.fromarray(arr).save(path, "AVIF", quality=QUALITY)
    return path.stat().st_size


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


def page(fname, body, preload, ts):
    html = (f"<!DOCTYPE html><html><head><meta charset='utf-8'>"
            f"<style>body{{margin:0;display:flex;flex-wrap:wrap}}"
            f".tile{{width:{ts}px;height:{ts}px}}</style></head><body>"
            f"{body}<script>const PRELOAD={json.dumps(preload)};</script>"
            f"{COMMON_JS}</body></html>")
    (WWW / fname).write_text(html, encoding="utf-8")


def main():
    WWW.mkdir(exist_ok=True)
    manifest = []
    for cls, ts in CLASSES.items():
        all_tiles = load_tiles(cls, max(COUNTS))
        for n in COUNTS:
            tiles = all_tiles[:n]
            # --- individual
            names = []
            total = 0
            for i, t in enumerate(tiles):
                nm = f"{cls}_{n}_t{i:03d}.avif"
                total += save_avif(t, WWW / nm)
                names.append(nm)
            body = "".join(f"<img class='tile' src='{nm}'>" for nm in names)
            page(f"individual_{cls}_{n}.html", body, names, ts)
            manifest.append({"cls": cls, "n": n, "cond": "individual",
                             "encoded_bytes": total, "files": n})
            # --- atlas1 and atlas4
            for chunks in (1, 4):
                if chunks == 4 and n < 40:
                    continue
                per = math.ceil(n / chunks)
                total, divs, preload = 0, [], []
                for c in range(chunks):
                    sub = tiles[c * per:(c + 1) * per]
                    if not sub:
                        continue
                    atlas, coords = build_atlas(sub)
                    nm = f"atlas_{cls}_{n}_c{chunks}_{c}.avif"
                    total += save_avif(atlas, WWW / nm)
                    preload.append(nm)
                    for (x, y) in coords:
                        divs.append(f"<div class='tile' style=\"background-image:url({nm});"
                                    f"background-position:-{x}px -{y}px\"></div>")
                page(f"atlas{chunks}_{cls}_{n}.html", "".join(divs), preload, ts)
                manifest.append({"cls": cls, "n": n, "cond": f"atlas{chunks}",
                                 "encoded_bytes": total, "files": chunks})
    json.dump(manifest, (WWW / "manifest.json").open("w"), indent=1)
    for m in manifest:
        print(m)


if __name__ == "__main__":
    main()
