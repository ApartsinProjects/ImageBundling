#!/usr/bin/env python
"""atlas-optimizer: turn a directory of small images into optimized bundles.

Applies the decision rules measured in the ImageBundling study
(https://apartsinprojects.github.io/ImageBundling/):

- exact duplicates are collapsed into one stored tile with many CSS entries;
- small LOSSY tiles (<= --atlas-max-px, default 130) with uniform dimensions are
  packed into WebP pixel atlases (byte saving grows as tiles shrink; ~15% for 56px
  photos, up to ~17% for 72px flat art at WebP; requests collapse to ~1 per chunk);
- larger lossy tiles and ALL lossless tiles go into a byte-bundle (concatenation of
  individually-encoded files + offset index): zero byte penalty, requests collapse
  to one (pixel-atlasing lossless or large-photo content costs bytes, so it is
  never chosen for them);
- groups are split by update cadence first (whole-bundle cache invalidation), then
  chunked (default 4) for loss resilience and bounded invalidation blast radius;
- tiny groups (< --min-group) stay as individual files.

Usage:
  python atlas_optimizer.py INPUT_DIR --out OUT_DIR
      [--manifest manifest.json] [--quality 80] [--chunks 4]
      [--atlas-max-px 130] [--min-group 10]

Optional manifest.json: { "<filename>": {"cadence": "stable"|"weekly"|...,
                                          "lossless": true|false } }
Outputs: atlas_*.webp / bundle_*.bin+json, atlas.css, usage.html, report.json.
"""
import argparse
import hashlib
import io
import json
import math
import re
from collections import defaultdict
from pathlib import Path

import numpy as np
from PIL import Image


def slug(name):
    return re.sub(r"[^a-zA-Z0-9_-]", "-", Path(name).stem)


def load_dir(d, manifest):
    tiles = []
    for f in sorted(Path(d).iterdir()):
        if f.suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"):
            continue
        im = Image.open(f)
        has_alpha = im.mode in ("RGBA", "LA", "P") and (
            im.convert("RGBA").getextrema()[3][0] < 255)
        im = im.convert("RGBA" if has_alpha else "RGB")
        meta = manifest.get(f.name, {})
        lossless = meta.get("lossless",
                            f.suffix.lower() in (".png", ".gif", ".bmp"))
        tiles.append({"name": f.name, "im": im, "w": im.width, "h": im.height,
                      "lossless": bool(lossless), "alpha": has_alpha,
                      "cadence": meta.get("cadence", "default"),
                      "md5": hashlib.md5(np.asarray(im).tobytes()).hexdigest()})
    return tiles


def encode(im, lossless, quality):
    b = io.BytesIO()
    if lossless:
        im.save(b, "WEBP", lossless=True, quality=100, method=6)
    else:
        im.save(b, "WEBP", quality=quality, method=6)
    return b.getvalue()


def strip_atlas_bytes(reps):
    """Total bytes of a WebP-lossless vertical strip (1 tile wide), chunked to fit
    WebP's 16383px dimension cap. Used only to size-compare against a byte-bundle."""
    th = reps[0]["h"]
    per = max(1, 16000 // th)
    total = 0
    for i in range(0, len(reps), per):
        sub = reps[i:i + per]
        strip = Image.new(sub[0]["im"].mode, (sub[0]["w"], sum(t["h"] for t in sub)))
        y = 0
        for t in sub:
            strip.paste(t["im"], (0, y))
            y += t["h"]
        b = io.BytesIO()
        strip.save(b, "WEBP", lossless=True, quality=100, method=6)
        total += len(b.getvalue())
    return total


def pack_atlas(reps, quality, out_path):
    n = len(reps)
    tw, th = reps[0]["w"], reps[0]["h"]
    cols = math.ceil(math.sqrt(n))
    rows = math.ceil(n / cols)
    mode = "RGBA" if any(t["alpha"] for t in reps) else "RGB"
    bg = (255, 255, 255, 0) if mode == "RGBA" else (255, 255, 255)
    atlas = Image.new(mode, (cols * tw, rows * th), bg)
    coords = {}
    for i, t in enumerate(reps):
        r, c = divmod(i, cols)
        atlas.paste(t["im"].convert(mode), (c * tw, r * th))
        coords[t["name"]] = (c * tw, r * th)
    blob = encode(atlas, False, quality)
    out_path.write_bytes(blob)
    return coords, len(blob)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("input")
    ap.add_argument("--out", required=True)
    ap.add_argument("--manifest")
    ap.add_argument("--quality", type=int, default=80)
    ap.add_argument("--chunks", type=int, default=4)
    ap.add_argument("--atlas-max-px", type=int, default=130)
    ap.add_argument("--min-group", type=int, default=10)
    ap.add_argument("--lossy-png", action="store_true",
                    help="treat PNG inputs as lossy-encodable (flat art like icons "
                         "usually survives WebP q80 visually; default is the safe "
                         "lossless track)")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    manifest = json.load(open(args.manifest)) if args.manifest else {}
    tiles = load_dir(args.input, manifest)
    if args.lossy_png:
        for t in tiles:
            if t["name"] not in manifest:
                t["lossless"] = False
    if not tiles:
        raise SystemExit("no images found")

    # --- dedup: one representative per pixel-identical group
    by_md5 = defaultdict(list)
    for t in tiles:
        by_md5[t["md5"]].append(t)
    reps, aliases = [], {}   # aliases: name -> representative name
    for group in by_md5.values():
        rep = group[0]
        reps.append(rep)
        for t in group[1:]:
            aliases[t["name"]] = rep["name"]

    # --- grouping: (cadence, lossless, dims-bucket)
    groups = defaultdict(list)
    for t in reps:
        groups[(t["cadence"], t["lossless"], (t["w"], t["h"]))].append(t)

    css, report, usage_snippets = [], [], []
    alias_count = defaultdict(int)          # representative name -> extra copies
    for name, rep in aliases.items():
        alias_count[rep] += 1
    for (cadence, lossless, (w, h)), members in sorted(groups.items()):
        gname = f"{cadence}_{'ll' if lossless else 'lossy'}_{w}x{h}"
        # baseline: every ORIGINAL file (duplicates included) served individually
        individual_bytes = sum(
            len(encode(t["im"], lossless, args.quality)) * (1 + alias_count[t["name"]])
            for t in members)
        small = max(w, h) <= args.atlas_max_px
        n = len(members)
        if n < args.min_group:
            cond = "individual"
            total = individual_bytes
            files = n
            for t in members:
                (out / t["name"]).write_bytes(encode(t["im"], lossless, args.quality))
        elif not lossless and small:
            cond = "pixel-atlas"
            k = 1 if n < 40 else args.chunks
            per = math.ceil(n / k)
            total, files = 0, 0
            for c in range(k):
                sub = members[c * per:(c + 1) * per]
                if not sub:
                    continue
                nm = f"atlas_{gname}_{c}.webp"
                coords, b = pack_atlas(sub, args.quality, out / nm)
                total += b
                files += 1
                for t in sub:
                    x, y = coords[t["name"]]
                    css.append(f".ib-{slug(t['name'])}{{background-image:url({nm});"
                               f"background-position:-{x}px -{y}px;"
                               f"width:{w}px;height:{h}px}}")
            usage_snippets.append(
                f"<!-- {gname}: <span class='ib-NAME'></span> per tile -->")
        elif lossless and strip_atlas_bytes(members) < individual_bytes:
            # measured tiebreak: a WebP-lossless vertical strip beats the byte-bundle
            # for this group (evaluated out-of-sample at 0% regret vs an oracle).
            cond = "strip-atlas"
            k = 1 if n < 40 else args.chunks
            per = math.ceil(n / k)
            total, files = 0, 0
            for c in range(k):
                sub = members[c * per:(c + 1) * per]
                if not sub:
                    continue
                nm = f"strip_{gname}_{c}.webp"
                strip = Image.new(sub[0]["im"].mode, (w, sum(t["h"] for t in sub)))
                y = 0
                for t in sub:
                    strip.paste(t["im"], (0, y))
                    css.append(f".ib-{slug(t['name'])}{{background-image:url({nm});"
                               f"background-position:0px -{y}px;width:{w}px;height:{h}px}}")
                    y += t["h"]
                b = io.BytesIO()
                strip.save(b, "WEBP", lossless=True, quality=100, method=6)
                (out / nm).write_bytes(b.getvalue())
                total += len(b.getvalue())
                files += 1
            usage_snippets.append(
                f"<!-- {gname}: <span class='ib-NAME'></span> per tile (strip atlas) -->")
        else:
            cond = "byte-bundle"
            k = 1 if n < 40 else args.chunks
            per = math.ceil(n / k)
            total, files = 0, 0
            for c in range(k):
                sub = members[c * per:(c + 1) * per]
                if not sub:
                    continue
                nm = f"bundle_{gname}_{c}"
                offs, off = {}, 0
                with (out / f"{nm}.bin").open("wb") as f:
                    for t in sub:
                        blob = encode(t["im"], lossless, args.quality)
                        f.write(blob)
                        offs[t["name"]] = [off, len(blob)]
                        off += len(blob)
                json.dump(offs, (out / f"{nm}.json").open("w"))
                total += off
                files += 1
            usage_snippets.append(
                f"<!-- {gname}: fetch {nm}.bin + {nm}.json, slice, blob-URL each tile -->")
        report.append({
            "group": gname, "condition": cond, "tiles": n,
            "duplicates_folded": sum(alias_count[t["name"]] for t in members),
            "requests": files, "bytes_out": total,
            "bytes_if_individual": individual_bytes,
            "saving_pct": round(100 * (1 - total / individual_bytes), 1)
            if individual_bytes else 0.0})

    # alias CSS entries point at the representative's region/file
    rep_rule = {r.split("{")[0][1:]: r for r in css}
    for name, rep in aliases.items():
        rule = rep_rule.get(f"ib-{slug(rep)}")
        if rule:
            css.append(f".ib-{slug(name)}" + "{" + rule.split("{", 1)[1])

    (out / "atlas.css").write_text("\n".join(css), encoding="utf-8")
    loader = """<link rel="stylesheet" href="atlas.css">
<!-- atlas tiles: --> <span class="ib-TILENAME"></span>
<!-- byte-bundle tiles: -->
<script>
async function loadBundle(base) {
  const [buf, offs] = await Promise.all([
    fetch(base + '.bin').then(r => r.arrayBuffer()),
    fetch(base + '.json').then(r => r.json())]);
  const urls = {};
  for (const [name, [o, l]] of Object.entries(offs))
    urls[name] = URL.createObjectURL(new Blob([buf.slice(o, o + l)],
                                              {type: 'image/webp'}));
  return urls;  // urls[filename] -> use as <img src>
}
</script>
"""
    (out / "usage.html").write_text(loader + "\n".join(usage_snippets),
                                    encoding="utf-8")
    json.dump({"aliases": aliases, "groups": report},
              (out / "report.json").open("w"), indent=1)
    tot_out = sum(g["bytes_out"] for g in report)
    tot_ind = sum(g["bytes_if_individual"] for g in report)
    tot_req = sum(g["requests"] for g in report)
    print(f"{len(tiles)} images ({len(aliases)} duplicates folded) -> "
          f"{tot_req} requests, {tot_out:,} B "
          f"({100 * (1 - tot_out / tot_ind):+.1f}% vs individual files)")
    for g in report:
        print(f"  {g['group']:28} {g['condition']:12} tiles={g['tiles']:4} "
              f"req={g['requests']:2} saving={g['saving_pct']:+.1f}%")


if __name__ == "__main__":
    main()
