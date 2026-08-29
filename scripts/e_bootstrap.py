"""M4/M3 resolution: randomized-subset bootstrap of the matched-quality saving.

Instead of one deterministic N-tile subset, draw K random subsets of size N from the
full pool and report the atlas-vs-individual saving as median + 95% bootstrap CI. Turns
Table 1's point estimates into distributions and shows the tile-size crossover is not a
single-subset artifact. Runs the photo size sweep (56/112/224 px) for JPEG and WebP, the
cells where the crossover and the WebP sign change live.
"""
import io, json, math, hashlib, random
from pathlib import Path
import numpy as np
from PIL import Image
import static_study as ss

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "results" / "static" / "e_bootstrap"; OUT.mkdir(parents=True, exist_ok=True)
K = 20   # random subsets per cell


def enc(arr, codec, q):
    b = io.BytesIO()
    if codec == "jpeg":
        Image.fromarray(arr).save(b, "JPEG", quality=q, optimize=True)
    else:
        Image.fromarray(arr).save(b, "WEBP", quality=q, method=6)
    return b.getvalue()


def grid(tiles):
    n = len(tiles); th, tw, _ = tiles[0].shape
    cols = math.ceil(math.sqrt(n)); rows = math.ceil(n / cols)
    a = np.full((rows * th, cols * tw, 3), 255, np.uint8); coords = []
    for i, t in enumerate(tiles):
        r, c = divmod(i, cols); a[r*th:(r+1)*th, c*tw:(c+1)*tw] = t; coords.append((c*tw, r*th))
    return a, coords


def matched_saving(tiles, codec, target=0.97):
    th, tw, _ = tiles[0].shape
    pa, pi = [], []
    for q in (35, 50, 65, 80, 90):
        atlas, coords = grid(tiles)
        ba = enc(atlas, codec, q)
        dec = np.asarray(Image.open(io.BytesIO(ba)).convert("RGB"))
        sa = np.mean([ss.ssim(t, dec[y:y+th, x:x+tw]) for t, (x, y) in zip(tiles, coords)])
        bi, si = 0, []
        for t in tiles:
            bt = enc(t, codec, q); bi += len(bt)
            si.append(ss.ssim(t, np.asarray(Image.open(io.BytesIO(bt)).convert("RGB"))))
        pa.append((float(sa), len(ba))); pi.append((float(np.mean(si)), bi))

    def at(p):
        p = sorted(p); xs = [a[0] for a in p]; ys = [np.log(a[1]) for a in p]
        return float(np.exp(np.interp(target, xs, ys))) if xs[0] <= target <= xs[-1] else None
    a, i = at(pa), at(pi)
    return 100 * (1 - a / i) if a and i else None


def load_pool(cls, size):
    pool = []
    seen = set()
    for f in sorted((ROOT / "assets" / cls).iterdir()):
        im = Image.open(f).convert("RGB")
        if size != im.width:
            im = im.resize((size, size), Image.LANCZOS)
        a = np.asarray(im)
        k = hashlib.md5(a.tobytes()).hexdigest()
        if k not in seen:
            seen.add(k); pool.append(a)
    return pool


rows = []
rng = random.Random(7)
for size in (56, 112, 224):
    pool = load_pool("photos", size)
    for N in (50, 200):
        for codec in ("jpeg", "webp"):
            savings = []
            for _ in range(K):
                sub = rng.sample(pool, N)
                s = matched_saving(sub, codec)
                if s is not None:
                    savings.append(s)
            savings.sort()
            lo = savings[int(0.025 * len(savings))]
            hi = savings[int(0.975 * len(savings))] if len(savings) > 1 else savings[0]
            med = float(np.median(savings))
            row = {"cls": "photos", "size": size, "N": N, "codec": codec,
                   "k_subsets": len(savings), "median_saving": round(med, 1),
                   "ci_lo": round(lo, 1), "ci_hi": round(hi, 1)}
            rows.append(row); print(row, flush=True)

json.dump(rows, (OUT / "results.json").open("w"), indent=1)
print("BOOTSTRAP DONE")
