"""Does arranging images in gradual-change order and encoding as VIDEO beat per-image
coding? Isolates the inter-frame gain: same codec (x264), all-intra vs inter (long GOP),
plus per-image JPEG and per-image AVIF baselines. Total bytes at matched mean per-frame
luma-SSIM 0.97.

Sets span a coherence spectrum:
  morph_seq        crossfade chain through 6 ImageNet keyframes (very coherent, upper bound)
  imagenet_cluster 48 images from one class, nearest-neighbor ordered (mildly coherent)
  imagenet_diverse 48 random images, nearest-neighbor ordered (incoherent)

Pre-registered: inter >> intra only on coherent sets; on diverse, inter ~ intra ~ per-image
AVIF (ordering can't make unrelated images predict each other -> "just use AVIF").
"""
import io
import json
import math
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image
import imageio_ffmpeg

sys.path.insert(0, str(Path(__file__).resolve().parent))
import e_predict as ep
import e_pivot_validate as pv

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "results" / "static" / "e_video"
OUT.mkdir(parents=True, exist_ok=True)
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

SIZE = 200
NF = 48
TARGET = 0.97
CRFS = [20, 26, 32, 38]
QUAL = [40, 60, 75, 88, 95]
RNG = np.random.default_rng(3)


def interp_at(pts):
    pts = sorted(pts)
    xs = [s for s, _ in pts]; ys = [math.log(b) for _, b in pts]
    return math.exp(float(np.interp(TARGET, xs, ys)))


def nn_order(frames):
    T = np.stack([np.asarray(Image.fromarray(f).resize((12, 12)), np.float32).ravel() for f in frames])
    used = [0]; rest = set(range(1, len(frames)))
    while rest:
        last = T[used[-1]]
        nxt = min(rest, key=lambda j: float(((T[j] - last) ** 2).sum()))
        used.append(nxt); rest.discard(nxt)
    return [frames[i] for i in used]


def morph_seq(pool):
    keys = [pool[RNG.integers(0, len(pool))].astype(np.float64) for _ in range(6)]
    frames = []
    per = NF // (len(keys) - 1)
    for a, b in zip(keys[:-1], keys[1:]):
        for t in range(per):
            al = t / per
            frames.append(np.clip((1 - al) * a + al * b, 0, 255).astype(np.uint8))
    return frames[:NF]


def perimage_bytes(frames, fmt):
    tot = 0.0
    for f in frames:
        pts = []
        for q in QUAL:
            b = io.BytesIO()
            im = Image.fromarray(f)
            if fmt == "JPEG":
                im.save(b, "JPEG", quality=q, optimize=True)
            else:
                im.save(b, "AVIF", quality=q)
            dec = np.asarray(Image.open(io.BytesIO(b.getvalue())).convert("RGB"))
            pts.append((ep.ssim(f, dec), len(b.getvalue())))
        tot += interp_at(pts)
    return tot


def video_bytes(frames, intra):
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        for i, f in enumerate(frames):
            Image.fromarray(f).save(td / f"f{i:04d}.png")
        pts = []
        for crf in CRFS:
            mp4 = td / f"v{crf}_{int(intra)}.mp4"
            cmd = [FFMPEG, "-y", "-loglevel", "error", "-framerate", "30",
                   "-i", str(td / "f%04d.png"), "-c:v", "libx264", "-crf", str(crf),
                   "-preset", "veryfast", "-pix_fmt", "yuv420p"]
            cmd += ["-g", "1"] if intra else ["-g", "9999", "-bf", "2"]
            cmd += [str(mp4)]
            subprocess.run(cmd, check=True)
            dec = td / f"d{crf}_{int(intra)}"
            dec.mkdir(exist_ok=True)
            subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-i", str(mp4),
                            "-pix_fmt", "rgb24", str(dec / "d%04d.png")], check=True)
            outs = sorted(dec.glob("d*.png"))
            sl = [ep.ssim(f, np.asarray(Image.open(o).convert("RGB")))
                  for f, o in zip(frames, outs)]
            pts.append((float(np.mean(sl)), mp4.stat().st_size))
        return interp_at(pts)


def build_sets(pool):
    # cluster: first NF images all from class 0 (build_pool loads class-by-class)
    cluster = nn_order([pool[i] for i in range(NF)])
    diverse = nn_order([pool[i] for i in RNG.choice(len(pool), NF, replace=False)])
    return {"morph_seq": morph_seq(pool),
            "imagenet_cluster": cluster,
            "imagenet_diverse": diverse}


def main():
    pool = pv.build_pool(SIZE)
    sets = build_sets(pool)
    results = {}
    for name, frames in sets.items():
        jpeg = perimage_bytes(frames, "JPEG")
        avif = perimage_bytes(frames, "AVIF")
        intra = video_bytes(frames, intra=True)
        inter = video_bytes(frames, intra=False)
        results[name] = {
            "frames": len(frames),
            "jpeg_bytes": int(jpeg), "avif_bytes": int(avif),
            "h264_intra_bytes": int(intra), "h264_inter_bytes": int(inter),
            "inter_vs_intra_pct": round(100 * (1 - inter / intra), 1),
            "inter_vs_avif_pct": round(100 * (1 - inter / avif), 1),
            "avif_vs_jpeg_pct": round(100 * (1 - avif / jpeg), 1),
        }
        r = results[name]
        print(f"\n=== {name} ({r['frames']} frames, matched SSIM 0.97) ===")
        print(f"  per-image JPEG {r['jpeg_bytes']:>8,}   per-image AVIF {r['avif_bytes']:>8,}")
        print(f"  H264 intra     {r['h264_intra_bytes']:>8,}   H264 inter     {r['h264_inter_bytes']:>8,}")
        print(f"  inter vs intra {r['inter_vs_intra_pct']:+.1f}%   "
              f"inter vs AVIF {r['inter_vs_avif_pct']:+.1f}%   "
              f"AVIF vs JPEG {r['avif_vs_jpeg_pct']:+.1f}%", flush=True)
    json.dump(results, (OUT / "results.json").open("w"), indent=1)
    print("\nVIDEO DONE")


if __name__ == "__main__":
    main()
