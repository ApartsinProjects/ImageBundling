"""E3.9 + E3.11: cross-file dictionary compression and delta updates.

E3.9  Bundle-then-compress: concatenate individually-encoded files (PNG and WebP)
      and compress the bundle with brotli -q11 and zstd -19 --long. Does a shared
      window recover cross-file redundancy that per-file serving loses?
E3.11b Trained dictionary: zstd dictionary trained on the tile-file corpus, applied
      per file (the per-file-delivery analogue of E3.9).
E3.11a Delta updates: simulate a deploy that replaces k tiles, and compare bytes a
      returning client must download under four strategies:
        monolithic pixel atlas  -> full re-download (entropy stream diverges)
        4-chunk pixel atlas     -> changed chunks re-download
        byte-bundle + zstd patch (old bundle as dictionary) -> ~changed tiles
        individual files        -> changed files only (the optimum)
Usage: python e39_e311_dict.py --tag e39 [--n 500]
"""
import argparse
import io
import json
import math
from pathlib import Path

import brotli
import numpy as np
import zstandard as zstd
from PIL import Image

import static_study as ss

ROOT = Path(__file__).resolve().parent.parent


def enc(t, codec, q):
    return ss.encode(Image.fromarray(t), codec, q)


def dedup(tiles):
    import hashlib
    seen, uniq = set(), []
    for t in tiles:
        k = hashlib.md5(t.tobytes()).hexdigest()
        if k not in seen:
            seen.add(k)
            uniq.append(t)
    return uniq


def zc(data, level=19, dict_data=None, long_log=27):
    p = zstd.ZstdCompressionParameters.from_level(level, window_log=long_log)
    c = zstd.ZstdCompressor(compression_params=p,
                            dict_data=zstd.ZstdCompressionDict(dict_data)
                            if dict_data else None)
    return len(c.compress(data))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="e39")
    ap.add_argument("--n", type=int, default=500)
    args = ap.parse_args()
    outdir = ROOT / "results" / "static" / args.tag
    outdir.mkdir(parents=True, exist_ok=True)
    out = (outdir / "results.jsonl").open("a")

    def emit(**kw):
        out.write(json.dumps(kw) + "\n")
        out.flush()
        print(kw, flush=True)

    for cls in ("emoji", "photos"):
        tiles, _ = ss.load_tiles(cls, args.n)
        if cls == "photos":
            tiles = dedup(tiles)
        n = len(tiles)
        for codec, q in (("png", None), ("webp", 80), ("webp_ll", None)):
            blobs = [enc(t, codec, q) for t in tiles]
            ind = sum(len(b) for b in blobs)
            cat = b"".join(blobs)
            emit(cls=cls, n=n, exp="E39", codec=codec, cond="individual", bytes=ind)
            emit(cls=cls, n=n, exp="E39", codec=codec, cond="bundle_raw", bytes=len(cat))
            emit(cls=cls, n=n, exp="E39", codec=codec, cond="bundle_brotli11",
                 bytes=len(brotli.compress(cat, quality=11)))
            emit(cls=cls, n=n, exp="E39", codec=codec, cond="bundle_zstd19long",
                 bytes=zc(cat))
            # E3.11b trained dictionary applied per file
            try:
                d = zstd.train_dictionary(112640, blobs)
                per = sum(zc(b, dict_data=d.as_bytes()) for b in blobs)
                emit(cls=cls, n=n, exp="E311b", codec=codec,
                     cond="perfile_zstd_traineddict", bytes=per + len(d.as_bytes()),
                     dict_bytes=len(d.as_bytes()))
            except Exception as e:
                emit(cls=cls, n=n, exp="E311b", codec=codec, cond="dict_failed",
                     error=str(e)[:100])

    # --- E3.11a delta updates (photos, webp lossy; the common product-grid case)
    tiles, _ = ss.load_tiles("photos", args.n)
    tiles = dedup(tiles)
    n = len(tiles)
    fresh, _ = ss.load_tiles("photos112", args.n)  # replacement pool, resized
    rng = np.random.default_rng(0)
    codec, q = "webp", 80
    blobs_v1 = [enc(t, codec, q) for t in tiles]
    bundle_v1 = b"".join(blobs_v1)

    def atlas_bytes(ts, k_chunks):
        per = math.ceil(len(ts) / k_chunks)
        outb = []
        for c in range(k_chunks):
            sub = ts[c * per:(c + 1) * per]
            if sub:
                a, _ = ss.build_atlas(sub, 0)
                outb.append(enc(a, codec, q))
        return outb

    atl1_v1 = atlas_bytes(tiles, 1)
    atl4_v1 = atlas_bytes(tiles, 4)
    for k in (5, 25, 50):
        if k > n:
            continue
        idx = rng.choice(n, k, replace=False)
        tiles_v2 = list(tiles)
        for j, i in enumerate(idx):
            im = Image.fromarray(fresh[j]).resize((224, 224), Image.LANCZOS)
            tiles_v2[int(i)] = np.asarray(im)
        blobs_v2 = [enc(t, codec, q) for t in tiles_v2]
        bundle_v2 = b"".join(blobs_v2)
        atl1_v2 = atlas_bytes(tiles_v2, 1)
        atl4_v2 = atlas_bytes(tiles_v2, 4)
        changed_chunks = sum(len(a) for a, b in zip(atl4_v2, atl4_v1) if a != b)
        emit(exp="E311a", k_changed=k, strategy="atlas1_full",
             bytes=sum(len(a) for a in atl1_v2))
        emit(exp="E311a", k_changed=k, strategy="atlas4_changed_chunks",
             bytes=changed_chunks)
        emit(exp="E311a", k_changed=k, strategy="bundle_zstd_patch",
             bytes=zc(bundle_v2, dict_data=bundle_v1))
        emit(exp="E311a", k_changed=k, strategy="individual_changed_files",
             bytes=sum(len(blobs_v2[int(i)]) for i in idx))
    print("E39/E311 DONE")


if __name__ == "__main__":
    main()
