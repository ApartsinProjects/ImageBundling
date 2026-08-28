"""Audit probes for the Phase 1 negative-savings findings.

A. Reproduce stored rows from scratch (harness reproducibility).
B. Empty-grid-cell slack: n=196 (14x14, zero slack) vs n=200 (15x14, 10 empty cells).
C. Positive control: 100 copies of ONE tile; atlas must massively win for EVERY codec.
D. Raw same-settings comparison table (no interpolation) for the codecs reported
   negative at matched quality, to show the sign is not an interpolation artifact.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import numpy as np
from PIL import Image

import static_study as ss

ROOT = Path(__file__).resolve().parent.parent
out = {}

def enc_ind(tiles, codec, q):
    return sum(len(ss.encode(Image.fromarray(t), codec, q)) for t in tiles)

def enc_atl(tiles, codec, q):
    atlas, coords = ss.build_atlas(tiles, 0)
    return len(ss.encode(Image.fromarray(atlas), codec, q))

# --- A: reproduce 4 stored rows
stored = [json.loads(l) for l in
          (ROOT / "results/static/phase1_photos/results.jsonl").open()]
probe = [r for r in stored if r["n"] == 50 and r["pad"] == 0 and
         ((r["codec"], r["quality"]) in [("webp", 80), ("avif", 50)])]
tiles50, _ = ss.load_tiles("photos", 50)
rep = []
for r in probe:
    b = (enc_ind if r["mode"] == "individual" else enc_atl)(tiles50, r["codec"], r["quality"])
    rep.append({"codec": r["codec"], "q": r["quality"], "mode": r["mode"],
                "stored": r["bytes_total"], "reproduced": b,
                "match": b == r["bytes_total"]})
out["A_reproduce"] = rep

# --- B: grid slack
tiles200, _ = ss.load_tiles("photos", 200)
for codec, q in [("webp", 80), ("png", None)]:
    full = enc_atl(tiles200[:196], codec, q)          # 14x14, no empty cells
    slack = enc_atl(tiles200[:200], codec, q)          # 15x14, 10 empty cells
    ind196 = enc_ind(tiles200[:196], codec, q)
    ind200 = enc_ind(tiles200[:200], codec, q)
    out[f"B_slack_{codec}"] = {
        "save_pct_n196_noslack": round(100 * (1 - full / ind196), 2),
        "save_pct_n200_slack": round(100 * (1 - slack / ind200), 2)}

# --- C: positive control, identical tiles
for cls in ["emoji", "photos"]:
    t1 = ss.load_tiles(cls, 1)[0][0]
    copies = [t1] * 100
    ctl = {}
    for codec, q in [("avif", 50), ("webp", 80), ("jpeg", 80), ("png", None),
                     ("webp_ll", None), ("jxl_ll", None) if ss.HAVE_JXL else ("png", None)]:
        i, a = enc_ind(copies, codec, q), enc_atl(copies, codec, q)
        ctl[f"{codec}:{q}"] = {"individual": i, "atlas": a,
                               "save_pct": round(100 * (1 - a / i), 1)}
    out[f"C_identical_{cls}"] = ctl

# --- D: raw same-settings signs for the negatives
raw = []
for cls, n in [("photos", 200), ("emoji", 200)]:
    tiles, _ = ss.load_tiles(cls, n)
    for codec, q in [("webp", 80), ("png", None), ("webp_ll", None),
                     ("jxl_ll", None) if ss.HAVE_JXL else ("png", None)]:
        i, a = enc_ind(tiles, codec, q), enc_atl(tiles, codec, q)
        raw.append({"cls": cls, "n": n, "codec": codec, "q": q,
                    "individual": i, "atlas": a,
                    "save_pct": round(100 * (1 - a / i), 1)})
out["D_raw_signs"] = raw

outfile = ROOT / "results" / "static" / "audit_negatives" / "audit.json"
outfile.parent.mkdir(parents=True, exist_ok=True)
json.dump(out, outfile.open("w"), indent=1)
print(json.dumps(out, indent=1))
