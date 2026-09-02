"""Validate (with CIs, on ImageNet-diverse content) the pivot hypothesis:

  Cluster an image collection by each tile's optimal quantization point (q*), code each
  cluster at its own quality, and beat a single shared quantizer at matched quality --
  AND drive that clustering cheaply from source features (so no per-tile encode sweep).

Data: imagenette2-160 (10 ImageNet classes), sampled evenly across classes for a WIDE
q* spread (the regime where a single operating point is most wasteful). Bootstrap over
random draws for confidence intervals.

Per draw, per codec, matched mean SSIM 0.97 (each cluster coded to the target; bytes
summed), we compare partitions of the SAME tiles:
  single      one atlas / one quality       (the paper's atlas)
  random_k    k random clusters             (isolates k-fold overhead)
  content_k   k k-means-on-thumbnail groups (the paper's cluster-pure criterion)
  affinity_k  k clusters by measured q*      (this idea, oracle clustering)
  feat_k      k clusters by feature->q* PREDICTION (this idea, cheap/deployable)
  individual  each tile at its own q*        (per-tile lower bound)

Pre-registered invariants:
  I1 random_k within a few % of single (random clusters share the whole-set q*).
  I2 for webp on large tiles, single costs MORE than individual (atlas penalty is real).
Pre-registered hypotheses (a null is informative):
  H1 affinity_k < single for webp, CI excludes 0.
  H2 affinity_k <= content_k (q*-affinity is a better criterion than visual similarity).
  H3 features predict q* clearly better than a constant, and feat_k approaches affinity_k.
  H4 the gain is larger here (wide q*) than the earlier Lorem-Picsum ~4%.
"""
import json
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import e_predict as ep
import e_jpeg_cluster as ec

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "results" / "static" / "e_pivot_validate"
OUT.mkdir(parents=True, exist_ok=True)
DATA = Path("E:/tmp/claude/E--Projects-ImageBudnling"
            "/67b7b589-2b72-4287-8c11-331d55592201/scratchpad/imagenette2-160/train")

PER_CLASS = 60          # pool size per class
SIZE = 128
CODECS = ["jpeg", "webp"]
KS = [4, 8, 16]
N = 150                 # tiles per bootstrap draw
B = 10                  # bootstrap draws
RNG = np.random.default_rng(0)


def build_pool(size):
    pool = []
    for cls in sorted(DATA.iterdir()):
        files = sorted(cls.glob("*.JPEG"))[:PER_CLASS]
        for f in files:
            im = Image.open(f).convert("RGB").resize((size, size), Image.LANCZOS)
            pool.append(np.asarray(im))
    return pool


def per_tile_features(t):
    y = (0.299 * t[..., 0] + 0.587 * t[..., 1] + 0.114 * t[..., 2]).astype(np.float64)
    gx = np.abs(np.diff(y, axis=1)).mean(); gy = np.abs(np.diff(y, axis=0)).mean()
    edge = (gx + gy) / 2 / 255
    F = np.abs(np.fft.fftshift(np.fft.fft2(y))) ** 2
    c = np.array(F.shape) // 2; r = min(F.shape) // 8
    yy, xx = np.ogrid[:F.shape[0], :F.shape[1]]
    low = ((yy - c[0]) ** 2 + (xx - c[1]) ** 2) <= r * r
    dct_hf = float(F[~low].sum() / (F.sum() + 1e-9))
    q = (t // 32).astype(np.int32)
    idx = (q[..., 0] * 64 + q[..., 1] * 8 + q[..., 2]).ravel()
    h = np.bincount(idx, minlength=512).astype(np.float64); h /= h.sum()
    ent = float(-(h[h > 0] * np.log2(h[h > 0])).sum())
    lum_var = float(y.var() / 255 ** 2)
    return [edge, dct_hf, ent, lum_var]


def probe_ssim(t, codec, q=75):
    return ep.ssim(t, ep.dec(ep.enc(t, codec, q)))


def predict_qstar(train_X, train_y, test_X):
    A = np.hstack([train_X, np.ones((len(train_X), 1))])
    coef, *_ = np.linalg.lstsq(A, train_y, rcond=None)
    return np.hstack([test_X, np.ones((len(test_X), 1))]) @ coef


def clusters_from_labels_or_order(tiles, key, k, mode):
    if mode == "order":                        # split sorted-by-key into k equal groups
        order = np.argsort(key)
        return [[tiles[i] for i in order[j * len(tiles) // k:(j + 1) * len(tiles) // k]]
                for j in range(k)]
    return ec.split_by(key, tiles, k)          # key is labels


def total_bytes(clusters, codec):
    return sum(ec.bytes_at_target(ec.atlas_curve(c, codec)) for c in clusters)


def rel(x, base):
    return 100 * (x / base - 1.0)


def main():
    pool = build_pool(SIZE)
    print(f"pool: {len(pool)} tiles @ {SIZE}px across 10 classes")
    rec = {c: {"single_vs_ind": [], "aff_vs_single": {k: [] for k in KS},
               "aff_vs_content": {k: [] for k in KS},
               "feat_vs_single": {k: [] for k in KS},
               "aff_vs_ind": {k: [] for k in KS},
               "rand_vs_single": {k: [] for k in KS},
               "qstar_sd": []} for c in CODECS}
    feat_eval = {c: {"feat_mae": [], "probe_mae": [], "const_mae": [],
                     "feat_r": [], "probe_r": []} for c in CODECS}

    for draw in range(B):
        idx = RNG.choice(len(pool), N, replace=False)
        tiles = [pool[i] for i in idx]
        feats = np.array([per_tile_features(t) for t in tiles])
        for codec in CODECS:
            qstar = np.array([ec.tile_qstar(t, codec) for t in tiles])
            rec[codec]["qstar_sd"].append(float(qstar.std()))
            probe = np.array([probe_ssim(t, codec) for t in tiles])

            # features -> q*  (held-out halves) : feature model vs 1-shot probe vs constant
            half = N // 2
            perm = RNG.permutation(N)
            tr, te = perm[:half], perm[half:]
            pf = predict_qstar(feats[tr], qstar[tr], feats[te])
            pp = predict_qstar(probe[tr, None], qstar[tr], probe[te, None])
            feat_eval[codec]["feat_mae"].append(float(np.mean(np.abs(pf - qstar[te]))))
            feat_eval[codec]["probe_mae"].append(float(np.mean(np.abs(pp - qstar[te]))))
            feat_eval[codec]["const_mae"].append(float(np.mean(np.abs(qstar[tr].mean() - qstar[te]))))
            feat_eval[codec]["feat_r"].append(float(np.corrcoef(pf, qstar[te])[0, 1]))
            feat_eval[codec]["probe_r"].append(float(np.corrcoef(pp, qstar[te])[0, 1]))

            # full-set feature-predicted q* (for feat_k clustering): leave-one-out-ish via
            # a single fit on all tiles (deployable proxy uses a pre-trained model; here we
            # fit on this draw, which if anything flatters feat_k only marginally)
            qpred = predict_qstar(feats, qstar, feats)

            single = total_bytes([tiles], codec)
            b_ind = ec.individual_bytes(tiles, codec, qstar) \
                if hasattr(ec, "individual_bytes") else \
                sum(len(ep.enc(t, codec, int(round(min(max(q, 50), 95))))) for t, q in zip(tiles, qstar))
            rec[codec]["single_vs_ind"].append(rel(single, b_ind))

            content_lab_cache = {}
            for k in KS:
                rp = RNG.permutation(N)
                rand = [[tiles[i] for i in rp[j::k]] for j in range(k)]
                if k not in content_lab_cache:
                    content_lab_cache[k] = ec.kmeans_thumbs(tiles, k)
                content = clusters_from_labels_or_order(tiles, content_lab_cache[k], k, "labels")
                aff = clusters_from_labels_or_order(tiles, qstar, k, "order")
                feat = clusters_from_labels_or_order(tiles, qpred, k, "order")

                b_rand = total_bytes(rand, codec)
                b_content = total_bytes(content, codec)
                b_aff = total_bytes(aff, codec)
                b_feat = total_bytes(feat, codec)
                rec[codec]["rand_vs_single"][k].append(rel(b_rand, single))
                rec[codec]["aff_vs_single"][k].append(rel(b_aff, single))
                rec[codec]["aff_vs_content"][k].append(rel(b_aff, b_content))
                rec[codec]["feat_vs_single"][k].append(rel(b_feat, single))
                rec[codec]["aff_vs_ind"][k].append(rel(b_aff, b_ind))
        print(f"  draw {draw+1}/{B} done", flush=True)

    def ci(v):
        a = np.array(v); m = a.mean()
        lo, hi = np.percentile(a, [2.5, 97.5])
        return [round(float(m), 2), round(float(lo), 2), round(float(hi), 2)]

    summary = {}
    for codec in CODECS:
        r = rec[codec]; fe = feat_eval[codec]
        summary[codec] = {
            "qstar_sd": ci(r["qstar_sd"]),
            "single_vs_individual": ci(r["single_vs_ind"]),
            "by_k": {k: {"affinity_vs_single": ci(r["aff_vs_single"][k]),
                         "affinity_vs_content": ci(r["aff_vs_content"][k]),
                         "feat_vs_single": ci(r["feat_vs_single"][k]),
                         "affinity_vs_individual": ci(r["aff_vs_ind"][k]),
                         "random_vs_single": ci(r["rand_vs_single"][k])} for k in KS},
            "qstar_prediction": {"feature_MAE": ci(fe["feat_mae"]),
                                 "probe1shot_MAE": ci(fe["probe_mae"]),
                                 "constant_MAE": ci(fe["const_mae"]),
                                 "feature_pearson": ci(fe["feat_r"]),
                                 "probe_pearson": ci(fe["probe_r"])},
        }
    json.dump(summary, (OUT / "results.json").open("w"), indent=1)

    for codec in CODECS:
        s = summary[codec]
        print(f"\n===== {codec.upper()} @ {SIZE}px  (mean [95% CI], neg = fewer bytes) =====")
        print(f"  q* spread sd            {s['qstar_sd']}")
        print(f"  single vs individual    {s['single_vs_individual']}")
        for k in KS:
            bk = s["by_k"][k]
            print(f"  k={k:>2}: affinity vs single {bk['affinity_vs_single']}  "
                  f"vs content {bk['affinity_vs_content']}  "
                  f"feat vs single {bk['feat_vs_single']}  "
                  f"aff vs individual {bk['affinity_vs_individual']}")
        qp = s["qstar_prediction"]
        print(f"  q* prediction MAE: features {qp['feature_MAE']}  1-shot probe {qp['probe1shot_MAE']}"
              f"  constant {qp['constant_MAE']}")
        print(f"  q* prediction Pearson: features {qp['feature_pearson']}  probe {qp['probe_pearson']}")
    print("\nPIVOT-VALIDATE DONE")


if __name__ == "__main__":
    main()
