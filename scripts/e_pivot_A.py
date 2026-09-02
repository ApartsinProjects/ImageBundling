"""Experiment A (go/no-go for a pivot): does optimizing the JPEG quantization table on
the PERCEPTUAL metric (SSIM), per cluster, cut a collection's total bytes enough to
justify a pivot? This is the lever the literature says matters (JQF ~23%, Guetzli ~30-45%)
and the one I earlier tested WRONG (MSE-energy, which lost).

Method: reshape the standard luma table by a per-radial-band multiplier (8 DOF), optimize
those multipliers by coordinate descent to MINIMIZE bytes at matched mean SSIM 0.97, driven
by SSIM. The grid INCLUDES multiplier 1.0, so an optimized table can never beat itself into
being worse than standard -> every reported gain is >= 0 by construction; the question is
magnitude. JPEG only (qtable is JPEG-specific).

Conditions on ImageNet-diverse tiles (bytes at matched SSIM; lower = better):
  std_single        one atlas, standard table            (baseline)
  opt_single        one atlas, SSIM-optimized table      (table opt alone)
  std_affinity_k    q*-clustered, standard tables         (clustering alone, from run before)
  opt_affinity_k    q*-clustered, per-cluster SSIM-opt    (the full pivot method)
  individual_std    each tile at its own quality, std     (per-tile byte floor, std table)

Pre-registered decision rule: a pivot has legs only if opt_affinity_k beats std_single by
>= 15% on this diverse content. 8-15% marginal; < 8% means the perceptual-table lever adds
little over what we already have (chunking/clustering ~5%) -> pivot dead.

Invariant: with 1.0 in the grid, opt_* <= std_* at matched SSIM (optimizer >= identity).
"""
import json
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import e_predict as ep
import e_jpeg_share as es
import e_jpeg_cluster as ec
import e_pivot_validate as pv

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "results" / "static" / "e_pivot_A"
OUT.mkdir(parents=True, exist_ok=True)

SIZE = 128
N = 150
B = 3
K = 8
TARGET = 0.97
SCALES = [0.45, 0.7, 1.0, 1.5, 2.2, 3.2]
GRID = [0.6, 1.0, 1.6]          # band-multiplier grid (includes identity 1.0)
PASSES = 2
RNG = np.random.default_rng(1)

# radial band index (0..7) for each of the 64 natural-order DCT positions
_BAND = np.array([[min(7, int(round(math.hypot(u, v)))) for v in range(8)] for u in range(8)]).ravel()


def zz_to_nat(zz):
    nat = np.zeros(64)
    for i, z in enumerate(zz):
        nat[es.ZIGZAG[i]] = z
    return nat


def nat_to_zz(nat):
    return np.array([nat[es.ZIGZAG[i]] for i in range(64)])


def table_from_mult(std_luma_zz, mult):
    nat = zz_to_nat(std_luma_zz) * mult[_BAND]
    return nat_to_zz(nat)


def clip_tab(t):
    return np.clip(np.round(t), 1, 255)


def atlas_ms_bytes(tiles, qt):
    a, coords, (th, tw) = ec.atlas_of(tiles)
    d = es.enc(a, qtables=qt); dd = ep.dec(d)
    sl = [ep.ssim(t, dd[y:y + th, x:x + tw]) for t, (y, x) in zip(tiles, coords)]
    return float(np.mean(sl)), len(d)


def matched_bytes(tiles, shape_zz, std_chroma):
    pts = []
    for s in SCALES:
        qt = [clip_tab(shape_zz * s), clip_tab(np.array(std_chroma, float) * s)]
        pts.append(atlas_ms_bytes(tiles, qt))
    pts.sort()
    xs = [m for m, _ in pts]; ys = [math.log(b) for _, b in pts]
    clamp = TARGET < xs[0] or TARGET > xs[-1]
    return math.exp(float(np.interp(TARGET, xs, ys))), clamp


def optimize_table(tiles, std_luma, std_chroma):
    mult = np.ones(8)
    best, _ = matched_bytes(tiles, table_from_mult(std_luma, mult), std_chroma)
    for _ in range(PASSES):
        for band in range(8):
            trial_best, trial_mult = best, mult.copy()
            for g in GRID:
                m = mult.copy(); m[band] = g
                by, _ = matched_bytes(tiles, table_from_mult(std_luma, m), std_chroma)
                if by < trial_best:
                    trial_best, trial_mult = by, m
            best, mult = trial_best, trial_mult
    return best, mult


def main():
    pool = pv.build_pool(SIZE)
    std_luma, std_chroma = es.std_qtables(85)
    std_luma = np.array(std_luma, float)
    print(f"pool {len(pool)} @ {SIZE}px; std table q85")

    agg = {k: [] for k in ["std_single", "opt_single_gain", "std_aff_gain",
                           "opt_aff_gain", "opt_aff_vs_opt_single", "ind_vs_std_single",
                           "clamp"]}
    for draw in range(B):
        idx = RNG.choice(len(pool), N, replace=False)
        tiles = [pool[i] for i in idx]
        qstar = np.array([ec.tile_qstar(t, "jpeg") for t in tiles])
        order = np.argsort(qstar)
        clusters = [[tiles[i] for i in order[j * N // K:(j + 1) * N // K]] for j in range(K)]

        std_single, c0 = matched_bytes(tiles, table_from_mult(std_luma, np.ones(8)), std_chroma)
        opt_single, _ = optimize_table(tiles, std_luma, std_chroma)

        std_aff = sum(matched_bytes(c, table_from_mult(std_luma, np.ones(8)), std_chroma)[0]
                      for c in clusters)
        opt_aff = sum(optimize_table(c, std_luma, std_chroma)[0] for c in clusters)

        # per-tile byte floor, standard table (each tile at its own quality to hit target)
        ind = ec.individual_bytes(tiles, "jpeg", qstar)

        def g(x):
            return round(100 * (1 - x / std_single), 2)
        agg["std_single"].append(int(std_single))
        agg["opt_single_gain"].append(g(opt_single))
        agg["std_aff_gain"].append(g(std_aff))
        agg["opt_aff_gain"].append(g(opt_aff))
        agg["opt_aff_vs_opt_single"].append(round(100 * (1 - opt_aff / opt_single), 2))
        agg["ind_vs_std_single"].append(g(ind))
        agg["clamp"].append(bool(c0))
        print(f"  draw {draw+1}/{B}: opt_single {g(opt_single)}%  std_aff {g(std_aff)}%  "
              f"opt_aff {g(opt_aff)}%  ind {g(ind)}%", flush=True)

    def ms(v):
        a = np.array(v, float); return [round(a.mean(), 2), round(a.min(), 2), round(a.max(), 2)]
    summary = {"note": "gain = % fewer bytes vs std_single at matched SSIM 0.97 (JPEG, 128px, ImageNet-diverse)",
               "opt_single_gain": ms(agg["opt_single_gain"]),
               "std_affinity8_gain": ms(agg["std_aff_gain"]),
               "opt_affinity8_gain": ms(agg["opt_aff_gain"]),
               "opt_affinity_vs_opt_single": ms(agg["opt_aff_vs_opt_single"]),
               "individual_std_gain": ms(agg["ind_vs_std_single"]),
               "any_clamp": any(agg["clamp"])}
    json.dump(summary, (OUT / "results.json").open("w"), indent=1)

    print("\n=== Experiment A (JPEG, 128px, ImageNet-diverse) : % fewer bytes vs std single atlas ===")
    print(f"  table-opt alone (single atlas)      {summary['opt_single_gain']}")
    print(f"  clustering alone (std tables, k=8)   {summary['std_affinity8_gain']}")
    print(f"  FULL: clustering + per-cluster SSIM-opt table  {summary['opt_affinity8_gain']}")
    print(f"  (full vs table-opt-single)          {summary['opt_affinity_vs_opt_single']}")
    print(f"  individual files (std table) ref     {summary['individual_std_gain']}")
    m = summary["opt_affinity8_gain"][0]
    verdict = "PIVOT HAS LEGS (>=15%)" if m >= 15 else ("MARGINAL (8-15%)" if m >= 8 else
              "PIVOT DEAD (<8%): perceptual-table lever adds little over existing chunking/clustering")
    print(f"\n  DECISION: full-method gain {m}%  ->  {verdict}")
    print("A DONE")


if __name__ == "__main__":
    main()
