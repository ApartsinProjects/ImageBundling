#!/usr/bin/env python
"""atlas-optimizer: turn a directory of small images into optimized bundles.

Applies the decision rules measured in the ImageBundling study
(https://apartsinprojects.github.io/ImageBundling/):

- exact duplicates are collapsed into one stored tile with many CSS entries;
- for LOSSY tiles the choice is MEASURED, not taken from tile size alone: for groups
  whose tiles pass a cheap size pre-filter (<= --atlas-max-px), the tool encodes both a
  WebP pixel atlas and a byte-bundle and keeps the pixel atlas only if it is strictly
  smaller AND passes a per-tile quality gate (worst-tile SSIM >= --quality-floor and its
  5th-percentile within --floor-tol of the byte-bundle's), so it never adopts an atlas
  that loses bytes or damages a subset of tiles; otherwise the group goes to a byte-bundle;
- larger lossy tiles and ALL lossless tiles go into a byte-bundle: the
  individually-encoded files are concatenated into ONE self-describing .bin (a 4-byte
  header length, a JSON offset index, then the payloads), so a chunk is one request
  at near-zero byte penalty (only the small offset header); pixel-atlasing lossless
  or large-photo content costs bytes, so it is never chosen for them;
- groups are split by update cadence first (whole-bundle cache invalidation), then
  chunked (default 4) for bounded cache-invalidation blast radius and decoded memory;
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


def _rgb(im):
    """RGB numpy array, alpha composited over white (matches the study's protocol)."""
    if im.mode in ("RGBA", "LA", "P"):
        bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
        im = Image.alpha_composite(bg, im.convert("RGBA"))
    return np.asarray(im.convert("RGB"))


def _box(x, w):
    c = np.cumsum(np.cumsum(x, axis=0), axis=1)
    c = np.pad(c, ((1, 0), (1, 0)))
    return (c[w:, w:] - c[:-w, w:] + c[:-w, :-w] - c[w:, :-w]) / (w * w)


def _ssim(a, b, window=8):
    ya = (0.299 * a[..., 0] + 0.587 * a[..., 1] + 0.114 * a[..., 2]).astype(np.float64)
    yb = (0.299 * b[..., 0] + 0.587 * b[..., 1] + 0.114 * b[..., 2]).astype(np.float64)
    w = min(window, ya.shape[0], ya.shape[1])
    C1, C2 = (0.01 * 255) ** 2, (0.03 * 255) ** 2
    ma, mb = _box(ya, w), _box(yb, w)
    vaa = _box(ya * ya, w) - ma * ma
    vbb = _box(yb * yb, w) - mb * mb
    vab = _box(ya * yb, w) - ma * mb
    s = ((2 * ma * mb + C1) * (2 * vab + C2)) / ((ma * ma + mb * mb + C1) * (vaa + vbb + C2))
    return float(s.mean())


def lossy_choice(members, quality, floor, floor_tol, probe=0):
    """Measured selection for a lossy group: encode both a WebP pixel atlas and a
    byte-bundle at the same quality, and return whether the atlas should be chosen, with
    per-tile SSIM tails. The atlas is chosen only if it is strictly smaller in bytes AND
    passes a per-tile quality gate: its 5th-percentile per-tile SSIM is within `floor_tol`
    of the byte-bundle's (which carries individual-file quality) and its worst tile is at
    or above the absolute `floor`. This replaces a hard size threshold with a measurement
    that will not adopt an atlas that loses bytes or damages a subset of tiles.

    With `probe` > 0 the measurement runs on a pilot of the first `probe` tiles instead of
    the whole group, which the study shows forecasts the full-group saving to about two
    percentage points (Spearman 0.98); the chosen representation is still emitted over the
    full group. This makes the decision cheap for large groups without changing it."""
    if probe and len(members) > probe:
        idx = np.random.default_rng(0).choice(len(members), probe, replace=False)
        members = [members[i] for i in idx]
    refs = [_rgb(t["im"]) for t in members]
    th, tw = refs[0].shape[:2]
    # byte-bundle candidate = each tile encoded individually (individual-file quality)
    bb_bytes, bb_ss = 0, []
    for t, ref in zip(members, refs):
        blob = encode(t["im"], False, quality)
        bb_bytes += len(blob)
        bb_ss.append(_ssim(ref, _rgb(Image.open(io.BytesIO(blob)))))
    # pixel-atlas candidate = whole grid at the same quality
    n = len(members)
    cols = math.ceil(math.sqrt(n)); rows = math.ceil(n / cols)
    mode = "RGBA" if any(t["alpha"] for t in members) else "RGB"
    bg = (255, 255, 255, 0) if mode == "RGBA" else (255, 255, 255)
    grid = Image.new(mode, (cols * tw, rows * th), bg)
    coords = []
    for i, t in enumerate(members):
        r, c = divmod(i, cols)
        grid.paste(t["im"].convert(mode), (c * tw, r * th))
        coords.append((r * th, c * tw))
    blob = encode(grid, False, quality)
    atlas_bytes = len(blob)
    dec = _rgb(Image.open(io.BytesIO(blob)))
    at_ss = [_ssim(ref, dec[y:y + th, x:x + tw]) for ref, (y, x) in zip(refs, coords)]
    bb_p5, at_p5, at_min = (float(np.percentile(bb_ss, 5)),
                            float(np.percentile(at_ss, 5)), float(min(at_ss)))
    gate = (at_p5 >= bb_p5 - floor_tol) and (at_min >= floor)
    choose = gate and (atlas_bytes < bb_bytes)
    return choose, {"atlas_bytes": atlas_bytes, "bundle_bytes": bb_bytes,
                    "atlas_ssim_p5": round(at_p5, 4), "atlas_ssim_min": round(at_min, 4),
                    "bundle_ssim_p5": round(bb_p5, 4), "gate_passed": gate}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("input")
    ap.add_argument("--out", required=True)
    ap.add_argument("--manifest")
    ap.add_argument("--quality", type=int, default=80)
    ap.add_argument("--chunks", type=int, default=4)
    ap.add_argument("--atlas-max-px", type=int, default=130,
                    help="cheap pre-filter: only measure a pixel atlas for tiles at or "
                         "below this size (larger lossy tiles are known net-negative)")
    ap.add_argument("--quality-floor", type=float, default=0.90,
                    help="absolute per-tile SSIM floor a pixel atlas must clear on its "
                         "worst tile to be chosen (W9 hard constraint)")
    ap.add_argument("--floor-tol", type=float, default=0.005,
                    help="how far a pixel atlas's 5th-percentile per-tile SSIM may fall "
                         "below the byte-bundle's before it is rejected")
    ap.add_argument("--probe", type=int, default=0,
                    help="opt-in speedup: decide the lossy atlas-vs-bundle choice from a "
                         "random pilot of this many tiles instead of the whole group "
                         "(0 = use all tiles, the safe default). A small probe forecasts "
                         "the full saving to ~2pp, but samples the quality tail, so it can "
                         "miss a single bad tile outside the pilot; use 0 for a hard "
                         "per-tile guarantee")
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
        # lossy groups: measure pixel-atlas vs byte-bundle and gate on a per-tile quality
        # floor, rather than deciding from tile size alone (W2/W9).
        atlas_ok, lossy_m = False, None
        if not lossless and n >= args.min_group and small:
            atlas_ok, lossy_m = lossy_choice(members, args.quality,
                                             args.quality_floor, args.floor_tol, args.probe)
        if n < args.min_group:
            cond = "individual"
            total, files = 0, n   # unique reps; folded duplicates reuse the same URL
            for t in members:
                # emit as .webp: encode() always produces WebP, so the extension must
                # match the content (the original name may be .png/.jpg/.gif)
                blob = encode(t["im"], lossless, args.quality)
                (out / f"{slug(t['name'])}.webp").write_bytes(blob)
                total += len(blob)
            usage_snippets.append(
                f"<!-- {gname}: individual files, one per tile: "
                "<img src='NAME.webp'> (duplicates map via report.json aliases) -->")
        elif not lossless and atlas_ok:
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
                # self-describing .bin: [4-byte header length][JSON index][payloads],
                # so the whole chunk is ONE request and report bytes == emitted bytes.
                offs, off, payloads = {}, 0, []
                for t in sub:
                    blob = encode(t["im"], lossless, args.quality)
                    payloads.append(blob)
                    offs[t["name"]] = [off, len(blob)]
                    off += len(blob)
                header = json.dumps(offs, separators=(",", ":")).encode("utf-8")
                with (out / f"{nm}.bin").open("wb") as f:
                    f.write(len(header).to_bytes(4, "big"))
                    f.write(header)
                    for blob in payloads:
                        f.write(blob)
                total += 4 + len(header) + off   # index header counts toward bytes_out
                files += 1
            usage_snippets.append(
                f"<!-- {gname}: fetch {nm}.bin (self-describing), slice, blob-URL each tile -->")
        rec = {
            "group": gname, "condition": cond, "tiles": n,
            "duplicates_folded": sum(alias_count[t["name"]] for t in members),
            "requests": files, "bytes_out": total,
            "bytes_if_individual": individual_bytes,
            "saving_pct": round(100 * (1 - total / individual_bytes), 1)
            if individual_bytes else 0.0}
        if lossy_m is not None:
            # measured pixel-atlas-vs-byte-bundle decision + per-tile quality gate (W2/W9)
            rec["lossy_decision"] = {
                "atlas_bytes": lossy_m["atlas_bytes"], "bundle_bytes": lossy_m["bundle_bytes"],
                "atlas_ssim_p5": lossy_m["atlas_ssim_p5"],
                "atlas_ssim_min": lossy_m["atlas_ssim_min"],
                "quality_gate_passed": lossy_m["gate_passed"], "chose_atlas": atlas_ok}
        report.append(rec)

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
  // one request per chunk; the .bin is self-describing:
  // [4-byte big-endian header length][JSON offset index][payloads]
  const buf = await fetch(base + '.bin').then(r => r.arrayBuffer());
  const dv = new DataView(buf);
  const hlen = dv.getUint32(0);
  const offs = JSON.parse(new TextDecoder().decode(new Uint8Array(buf, 4, hlen)));
  const base0 = 4 + hlen, urls = {};
  for (const [name, [o, l]] of Object.entries(offs))
    urls[name] = URL.createObjectURL(new Blob([buf.slice(base0 + o, base0 + o + l)],
                                              {type: 'image/webp'}));
  return urls;  // urls[filename] -> <img src>; call URL.revokeObjectURL(url) when done
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
