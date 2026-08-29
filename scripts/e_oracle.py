"""Out-of-sample optimizer evaluation vs an offline oracle (SPE review item 1).

For each INDEPENDENT corpus (none used to calibrate the heuristic), enumerate a candidate
set of serving configurations, encode each at matched quality, and find the byte-optimal
(the oracle). Then apply the atlas_optimizer decision rule and report its choice, the
oracle's choice, and the optimizer's regret = optimizer_bytes / oracle_bytes - 1.

Candidate configs (per corpus, at matched per-tile SSIM 0.97 for lossy; exact for
lossless): individual files; grid atlas; vertical-strip atlas; byte-bundle; each in the
best of {webp-lossy, jpeg, png, webp-lossless} where the codec is admissible (alpha ->
no jpeg). This is the "reasonable candidate set the tool considers" the review asked for.
"""
import io, json, math, hashlib
from pathlib import Path
import numpy as np
from PIL import Image
import static_study as ss

ROOT = Path(__file__).resolve().parent.parent
OOS = ROOT / "assets_oos"
OUT = ROOT / "results" / "static" / "e_oracle"; OUT.mkdir(parents=True, exist_ok=True)

# corpus -> (tile size, has_alpha, class-label)
CORPORA = {
    "noto": (72, True, "flat-art"),
    "openmoji": (72, True, "flat-art"),
    "flags": (80, False, "flat-limited"),
    "flickr": (224, False, "photo"),
    "robo": (64, True, "avatar"),
}


def load(cls, size, has_alpha, cap=100):
    d = OOS / cls
    tiles = []
    for f in sorted(d.iterdir())[:cap]:
        im = Image.open(f)
        if has_alpha:
            im = im.convert("RGBA")
            im = Image.alpha_composite(Image.new("RGBA", im.size, (255,)*4), im)
        im = im.convert("RGB")
        if im.size != (size, size):
            im = im.resize((size, size), Image.LANCZOS)
        tiles.append(np.asarray(im))
    return tiles


def enc(arr, codec, q=None):
    b = io.BytesIO()
    if codec == "png":
        Image.fromarray(arr).save(b, "PNG", optimize=True)
    elif codec == "webpll":
        Image.fromarray(arr).save(b, "WEBP", lossless=True, quality=100, method=6)
    elif codec == "jpeg":
        Image.fromarray(arr).save(b, "JPEG", quality=q, optimize=True)
    else:
        Image.fromarray(arr).save(b, "WEBP", quality=q, method=6)
    return b.getvalue()


def grid(tiles):
    n = len(tiles); th, tw, _ = tiles[0].shape
    cols = math.ceil(math.sqrt(n)); rows = math.ceil(n/cols)
    a = np.full((rows*th, cols*tw, 3), 255, np.uint8); coords = []
    for i, t in enumerate(tiles):
        r, c = divmod(i, cols); a[r*th:(r+1)*th, c*tw:(c+1)*tw] = t; coords.append((c*tw, r*th))
    return a, coords


def strip(tiles):
    return np.concatenate(tiles, axis=0)


def matched_lossy(tiles, codec, layout, target=0.97):
    """bytes for a lossy layout at matched mean-tile SSIM; layout in {individual,grid,strip}."""
    th, tw, _ = tiles[0].shape
    pts = []
    for q in (35, 50, 65, 80, 90):
        if layout == "individual":
            blobs = [enc(t, codec, q) for t in tiles]
            b = sum(len(x) for x in blobs)
            s = np.mean([ss.ssim(t, np.asarray(Image.open(io.BytesIO(x)).convert("RGB")))
                         for t, x in zip(tiles, blobs)])
        else:
            arr = grid(tiles)[0] if layout == "grid" else strip(tiles)
            blob = enc(arr, codec, q); b = len(blob)
            dec = np.asarray(Image.open(io.BytesIO(blob)).convert("RGB"))
            if layout == "grid":
                _, coords = grid(tiles)
                s = np.mean([ss.ssim(t, dec[y:y+th, x:x+tw]) for t, (x, y) in zip(tiles, coords)])
            else:
                s = np.mean([ss.ssim(t, dec[i*th:(i+1)*th, :tw]) for i, t in enumerate(tiles)])
        pts.append((float(s), b))
    xs = sorted(pts)
    ss_x = [p[0] for p in xs]; by = [np.log(p[1]) for p in xs]
    if target < ss_x[0] or target > ss_x[-1]:
        return xs[0][1] if ss_x[0] > target else None
    return float(np.exp(np.interp(target, ss_x, by)))


def lossless_bytes(tiles, codec, layout):
    if layout == "individual":
        return sum(len(enc(t, codec)) for t in tiles)
    arr = grid(tiles)[0] if layout == "grid" else strip(tiles)
    return len(enc(arr, codec))


def byte_bundle(tiles, codec, q=80):
    # concatenation of individually-encoded files at matched quality is ~ individual bytes;
    # use the individual matched-quality total (zero-penalty request collapse).
    return matched_lossy(tiles, codec, "individual") if codec in ("webp", "jpeg") \
        else lossless_bytes(tiles, codec, "individual")


def dedup(tiles):
    seen, uniq = set(), []
    for t in tiles:
        k = hashlib.md5(t.tobytes()).hexdigest()
        if k not in seen:
            seen.add(k); uniq.append(t)
    return uniq


def optimizer_choice(tiles, size, has_alpha):
    """Replicate atlas_optimizer's routing rule (Section 6.3)."""
    u = dedup(tiles)
    dup_folZ = len(tiles) - len(u)
    small = size <= 130
    if has_alpha:  # lossless track (png/webpll)
        # optimizer routes small lossless flat art to byte-bundle (proven zero-penalty)
        cond = "byte-bundle(webpll)"
        b = byte_bundle(u, "webpll")
    elif small:
        cond = "pixel-atlas(webp)"
        b = matched_lossy(u, "webp", "grid")
    else:
        cond = "byte-bundle(webp)"
        b = byte_bundle(u, "webp")
    return cond, b, dup_folZ


def oracle(tiles, size, has_alpha):
    u = dedup(tiles)
    cands = {}
    lossy = [c for c in ("webp", "jpeg") if not has_alpha]  # jpeg only w/o alpha
    if not has_alpha:
        lossy = ["webp", "jpeg"]
    for codec in lossy:
        cands[f"individual({codec})"] = matched_lossy(u, codec, "individual")
        cands[f"grid-atlas({codec})"] = matched_lossy(u, codec, "grid")
        cands[f"byte-bundle({codec})"] = byte_bundle(u, codec)
    for codec in ("png", "webpll"):
        cands[f"individual({codec})"] = lossless_bytes(u, codec, "individual")
        cands[f"grid-atlas({codec})"] = lossless_bytes(u, codec, "grid")
        cands[f"strip-atlas({codec})"] = lossless_bytes(u, codec, "strip")
        cands[f"byte-bundle({codec})"] = byte_bundle(u, codec)
    cands = {k: v for k, v in cands.items() if v is not None}
    best = min(cands, key=cands.get)
    return best, cands[best], cands


rows = []
for cls, (size, has_alpha, label) in CORPORA.items():
    tiles = load(cls, size, has_alpha)
    if len(tiles) < 20:
        print(f"skip {cls}: only {len(tiles)} tiles"); continue
    ochoice, obytes, ncoll = optimizer_choice(tiles, size, has_alpha)
    bestname, bestbytes, allc = oracle(tiles, size, has_alpha)
    regret = round(100 * (obytes / bestbytes - 1), 1)
    ind_ref = allc.get("individual(webpll)") or allc.get("individual(webp)")
    row = {"corpus": cls, "class": label, "n": len(tiles), "size": size,
           "duplicates": ncoll,
           "optimizer_choice": ochoice, "optimizer_bytes": round(obytes),
           "oracle_choice": bestname, "oracle_bytes": round(bestbytes),
           "regret_pct": regret,
           "savings_vs_individual_pct": round(100*(1 - obytes/ind_ref), 1) if ind_ref else None,
           "all_candidates": {k: round(v) for k, v in sorted(allc.items(), key=lambda x: x[1])}}
    rows.append(row)
    print(f"{cls:9} opt={ochoice} ({round(obytes)}B) | oracle={bestname} ({round(bestbytes)}B) "
          f"| regret {regret}% | vs-individual {row['savings_vs_individual_pct']}%", flush=True)

json.dump(rows, (OUT / "results.json").open("w"), indent=1)
print("ORACLE DONE")
