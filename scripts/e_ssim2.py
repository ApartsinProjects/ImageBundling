"""SSIMULACRA2 robustness cross-check for the matched-quality photo crossover.

The main study matches quality by luma SSIM 0.97. A reviewer asks whether the WebP
photo crossover (positive at small tiles, negative near/above ~100 px) and JPEG's
persistent positive saving survive under a modern perceptual metric. We re-measure the
photo crossover with SSIMULACRA2 (reference Rust implementation ssimulacra2_rs, the
libjxl metric), for JPEG and WebP at 56/112/224 px.

SSIMULACRA2 is multi-scale and not well defined on a single 56 px tile, so quality is
scored on the FULL grid image: the atlas arm scores the decoded atlas against the
uncompressed reference grid; the individual arm encodes each tile separately, decodes,
reassembles the same grid, and scores that against the same reference grid. Both arms are
therefore scored as one properly-sized image against one reference (construct-matched).
Bytes are compared at a matched SSIMULACRA2 target by log-linear interpolation of each
arm's rate-distortion curve, exactly as the SSIM protocol does.
"""
import io
import json
import subprocess
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

import static_study as ss

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "results" / "static" / "e_ssim2"
OUT.mkdir(parents=True, exist_ok=True)
SS2 = str(Path.home() / ".cargo" / "bin" / "ssimulacra2_rs.exe")
QUALITIES = [30, 50, 65, 80, 90]
N = 100
SIZES = [("phase1_photos56", 56), ("phase1_photos112", 112), ("phase1_photos", 224)]
CODECS = ["jpeg", "webp"]
TARGETS = [50, 60, 70]  # matched SSIMULACRA2 operating points


def ss2_score(ref_arr, dist_arr):
    with tempfile.TemporaryDirectory() as d:
        pa, pb = Path(d) / "a.png", Path(d) / "b.png"
        Image.fromarray(ref_arr).save(pa)
        Image.fromarray(dist_arr).save(pb)
        r = subprocess.run([SS2, "image", str(pa), str(pb)],
                           capture_output=True, text=True)
        return float(r.stdout.split(":")[1].strip())


def grid_from_tiles(tiles):
    """Reassemble decoded tiles into the same pad=0 grid geometry build_atlas uses."""
    atlas, coords = ss.build_atlas(tiles, 0)
    return atlas.shape, coords


def bytes_at(points, target):
    """log-linear interpolation of bytes at a target ss2 score; None if out of range."""
    pts = sorted(points)
    xs = np.array([p[0] for p in pts])
    bb = np.log(np.array([float(p[1]) for p in pts]))
    if target < xs[0] or target > xs[-1]:
        return None
    return float(np.exp(np.interp(target, xs, bb)))


def main():
    rows = []
    for tag, size in SIZES:
        cls = "photos" if size == 224 else f"photos{size}"
        tiles, _ = ss.load_tiles(cls, N)
        th, tw, _ = tiles[0].shape
        # reference grid (uncompressed pixels, pad=0)
        ref_grid, coords = ss.build_atlas(tiles, 0)
        for codec in CODECS:
            curves = {"individual": [], "atlas": []}
            for q in QUALITIES:
                # individual arm: encode each tile alone, decode, paste into grid
                ind_bytes = 0
                ind_grid = np.full_like(ref_grid, 255)
                for t, (y, x) in zip(tiles, coords):
                    b = ss.encode(Image.fromarray(t), codec, q)
                    ind_bytes += len(b)
                    ind_grid[y:y + th, x:x + tw] = ss.decode(b)
                ind_ss2 = ss2_score(ref_grid, ind_grid)
                curves["individual"].append((ind_ss2, ind_bytes))
                # atlas arm: encode whole grid, decode, score
                ab = ss.encode(Image.fromarray(ref_grid), codec, q)
                atl_grid = ss.decode(ab)
                atl_ss2 = ss2_score(ref_grid, atl_grid)
                curves["atlas"].append((atl_ss2, len(ab)))
                print(f"{cls} {codec} q{q}: ind ss2={ind_ss2:.2f} ({ind_bytes} B)  "
                      f"atlas ss2={atl_ss2:.2f} ({len(ab)} B)")
            for target in TARGETS:
                bi = bytes_at(curves["individual"], target)
                ba = bytes_at(curves["atlas"], target)
                if bi is None or ba is None:
                    saving = None
                else:
                    saving = round(100 * (1 - ba / bi), 2)
                rows.append({"size": size, "codec": codec, "target": target,
                             "bytes_individual": round(bi) if bi else None,
                             "bytes_atlas": round(ba) if ba else None,
                             "saving_pct": saving})
            rows.append({"size": size, "codec": codec, "curves": curves})
    json.dump(rows, (OUT / "results.json").open("w"), indent=1)
    print("\n=== matched-SSIMULACRA2 savings (atlas vs individual) ===")
    print(f"{'size':>5} {'codec':6} " + " ".join(f"t={t:>3}" for t in TARGETS))
    for tag, size in SIZES:
        for codec in CODECS:
            cells = []
            for t in TARGETS:
                r = next((x for x in rows if x.get("size") == size and
                          x.get("codec") == codec and x.get("target") == t), None)
                v = r["saving_pct"] if r else None
                cells.append(f"{v:>6}" if v is not None else "    --")
            print(f"{size:>5} {codec:6} " + " ".join(cells))
    print("SSIM2 DONE")


if __name__ == "__main__":
    main()
