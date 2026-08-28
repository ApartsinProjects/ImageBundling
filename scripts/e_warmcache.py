"""Warm-cache churn: bytes a RETURNING client re-downloads per deploy, by strategy.

Models repeated visits: a client has version v cached; the site deploys v+1 with a
fraction p of tiles changed. For each serving strategy, compute the bytes the client
must fetch on the return visit (cache-hit content costs 0). Strategies:
  individual_immutable : content-addressed files; fetch only the changed files.
  atlas_1 / atlas_4 / atlas_16 : whole changed atlas chunk(s) re-fetched.
  byte_bundle_k(4)     : changed byte-bundle chunk(s) re-fetched.
  dict_delta           : whole bundle served as a zstd delta vs the cached prior bundle.
Averaged over 20 random deploys per churn rate. Photos (webp q80), 384 unique tiles.
"""
import io, json, math, hashlib
from pathlib import Path
import numpy as np
import zstandard as zstd
from PIL import Image
import static_study as ss

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "results" / "static" / "e_warmcache"; OUT.mkdir(parents=True, exist_ok=True)

photos,_ = ss.load_tiles("photos", 300)
seen, pool = set(), []
for t in photos:
    k = hashlib.md5(t.tobytes()).hexdigest()
    if k not in seen: seen.add(k); pool.append(t)
fresh,_ = ss.load_tiles("photos112", 300)  # replacement pool
tiles = pool[:200]
n = len(tiles); th, tw, _ = tiles[0].shape

def enc(t):
    b=io.BytesIO(); Image.fromarray(t).save(b,"WEBP",quality=80,method=6); return b.getvalue()

def chunk_bytes(ts, kchunks):
    per = math.ceil(len(ts)/kchunks); out=[]
    for c in range(kchunks):
        sub = ts[c*per:(c+1)*per]
        if not sub: continue
        a = np.full((math.ceil(len(sub)/math.ceil(math.sqrt(len(sub))))*th,
                     math.ceil(math.sqrt(len(sub)))*tw,3),255,np.uint8)
        cols=math.ceil(math.sqrt(len(sub)))
        for i,t in enumerate(sub):
            r,cc=divmod(i,cols); a[r*th:(r+1)*th,cc*tw:(cc+1)*tw]=t
        b=io.BytesIO(); Image.fromarray(a).save(b,"WEBP",quality=80,method=6); out.append(b.getvalue())
    return out

def bundlebin(ts, kchunks):
    per=math.ceil(len(ts)/kchunks); out=[]
    for c in range(kchunks):
        sub=ts[c*per:(c+1)*per]
        if sub: out.append(b"".join(enc(t) for t in sub))
    return out

def zdelta(new, old):
    c=zstd.ZstdCompressor(level=19, compression_params=zstd.ZstdCompressionParameters.from_level(19,window_log=27),
                          dict_data=zstd.ZstdCompressionDict(old))
    return len(c.compress(new))

blobs_v1=[enc(t) for t in tiles]
bundle_v1=b"".join(blobs_v1)
atl1_v1=chunk_bytes(tiles,1); atl4_v1=chunk_bytes(tiles,4); atl16_v1=chunk_bytes(tiles,16)
bb4_v1=bundlebin(tiles,4)
total_fresh = sum(len(b) for b in blobs_v1)

rng=np.random.default_rng(7)
rows=[]
for p in (0.01,0.02,0.05,0.10,0.20):
    k=max(1,round(p*n))
    acc={s:[] for s in ("individual","atlas1","atlas4","atlas16","bytebundle4","dict_delta")}
    for _ in range(20):
        idx=rng.choice(n,k,replace=False)
        v2=list(tiles)
        for j,i in enumerate(idx):
            v2[int(i)]=np.asarray(Image.fromarray(fresh[j%len(fresh)]).resize((tw,th),Image.LANCZOS))
        blobs2=[enc(t) for t in v2]; bundle2=b"".join(blobs2)
        acc["individual"].append(sum(len(blobs2[int(i)]) for i in idx))
        for kc,v1c,name in [(1,atl1_v1,"atlas1"),(4,atl4_v1,"atlas4"),(16,atl16_v1,"atlas16")]:
            v2c=chunk_bytes(v2,kc)
            acc[name].append(sum(len(a) for a,b in zip(v2c,v1c) if a!=b))
        bb2=bundlebin(v2,4)
        acc["bytebundle4"].append(sum(len(a) for a,b in zip(bb2,bb4_v1) if a!=b))
        acc["dict_delta"].append(zdelta(bundle2,bundle_v1))
    row={"churn_pct":round(p*100,1),"tiles_changed":k,
         **{s:round(float(np.mean(v)))for s,v in acc.items()}}
    rows.append(row); print(row,flush=True)

json.dump({"total_fresh_download":total_fresh,"rows":rows},(OUT/"results.json").open("w"),indent=1)
print("WARMCACHE DONE, full fresh bundle =",total_fresh,"bytes")
