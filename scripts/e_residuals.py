"""Test the residual 'can we make the losing pixel-atlas cases win' questions.

R1 PNG diverse photos: grid vs strip vs row-sorted-strip vs individual. Can any
   layout make the PNG pixel-atlas beat individual files on diverse photos?
R2 lossless WebP diverse photos: grid vs strip vs individual.
R3 JPEG shared-tables vs plain atlas vs individual-optimized: does sharing ONE
   pooled-optimized-table set (approx via the atlas's single optimized stream) or
   fixed-table abbreviated format ever beat the plain grid atlas?
All on 120 deduplicated 224px photos; lossless byte-exact; JPEG at equal q80.
"""
import io, json, math, hashlib
from pathlib import Path
import numpy as np
from PIL import Image
import static_study as ss

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "results" / "static" / "e_residuals"; OUT.mkdir(parents=True, exist_ok=True)

photos,_ = ss.load_tiles("photos", 300)
seen, pool = set(), []
for t in photos:
    k = hashlib.md5(t.tobytes()).hexdigest()
    if k not in seen: seen.add(k); pool.append(t)
tiles = pool[:120]
n = len(tiles); th, tw, _ = tiles[0].shape

def enc(arr, fmt, **kw):
    b = io.BytesIO(); Image.fromarray(arr).save(b, fmt, **kw); return len(b.getvalue())

def grid(ts):
    cols = math.ceil(math.sqrt(len(ts))); rows = math.ceil(len(ts)/cols)
    a = np.full((rows*th, cols*tw, 3), 255, np.uint8)
    for i,t in enumerate(ts):
        r,c = divmod(i,cols); a[r*th:(r+1)*th, c*tw:(c+1)*tw] = t
    return a

def strip(ts):
    return np.concatenate(ts, axis=0)

# row-sort: order tiles by mean luma so vertically-adjacent tiles are similar
luma = [float(np.mean(0.299*t[...,0]+0.587*t[...,1]+0.114*t[...,2])) for t in tiles]
sorted_tiles = [tiles[i] for i in np.argsort(luma)]

rows = []
def emit(**k): rows.append(k); print(k, flush=True)

# R1 PNG
png_ind = sum(enc(t,"PNG",optimize=True) for t in tiles)
emit(test="R1_png", cond="individual", bytes=png_ind, save_pct=0.0)
for name, arr in [("grid",grid(tiles)),("strip",strip(tiles)),
                  ("strip_lumasorted",strip(sorted_tiles))]:
    b = enc(arr,"PNG",optimize=True)
    emit(test="R1_png", cond=name, bytes=b, save_pct=round(100*(1-b/png_ind),1))

# R2 lossless WebP. WebP max dim 16383, so strip is chunked into pieces that fit.
def webpll_chunked_strip(ts):
    per = 16000 // th  # tiles per strip chunk
    total = 0
    for i in range(0, len(ts), per):
        total += enc(strip(ts[i:i+per]), "WEBP", lossless=True, quality=100, method=6)
    return total
wll_ind = sum(enc(t,"WEBP",lossless=True,quality=100,method=6) for t in tiles)
emit(test="R2_webpll", cond="individual", bytes=wll_ind, save_pct=0.0)
emit(test="R2_webpll", cond="grid", bytes=enc(grid(tiles),"WEBP",lossless=True,quality=100,method=6),
     save_pct=round(100*(1-enc(grid(tiles),"WEBP",lossless=True,quality=100,method=6)/wll_ind),1))
for name, ts in [("strip_chunked",tiles),("strip_lumasorted_chunked",sorted_tiles)]:
    b = webpll_chunked_strip(ts)
    emit(test="R2_webpll", cond=name, bytes=b, save_pct=round(100*(1-b/wll_ind),1))

# R3 JPEG shared tables vs atlas (equal q80)
def jpeg(t, opt):
    b=io.BytesIO(); Image.fromarray(t).save(b,"JPEG",quality=80,optimize=opt); return b.getvalue()
ind_opt = sum(len(jpeg(t,True)) for t in tiles)
atlas_opt = enc(grid(tiles),"JPEG",quality=80,optimize=True)
# shared fixed-table abbreviated bundle
blobs=[jpeg(t,False) for t in tiles]
ref=blobs[0]; pref=len(ref)
for b in blobs:
    m=min(pref,len(b)); i=0
    while i<m and b[i]==ref[i]: i+=1
    pref=i
shared=pref+sum(len(b)-pref for b in blobs)+4*len(blobs)
emit(test="R3_jpeg", cond="individual_optimized", bytes=ind_opt, save_pct=0.0)
emit(test="R3_jpeg", cond="grid_atlas_optimized", bytes=atlas_opt, save_pct=round(100*(1-atlas_opt/ind_opt),1))
emit(test="R3_jpeg", cond="shared_tables_bundle", bytes=shared, save_pct=round(100*(1-shared/ind_opt),1),
     vs_atlas=round(100*(1-shared/atlas_opt),1))

json.dump(rows,(OUT/"results.json").open("w"),indent=1)
print("RESIDUALS DONE")
