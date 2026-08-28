"""Modal-side wrapper for E3.1-dedup: ordering study on the deduplicated photo set."""
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, "/app")
try:
    import pillow_avif  # noqa: F401
except ImportError:
    pass

zipfile.ZipFile("/app/assets_bundle.zip").extractall("/assets")

import e31_ordering  # noqa: E402

sys.argv = ["e31_ordering.py", "--tag", "e31_dedup2", "--dedup",
            "--classes", "photos", "--n", "500",
            "--codecs", "webp_ll",
            "--orders", "baseline,kmeans"]
e31_ordering.main()

for line in Path("/results/static/e31_dedup2/results.jsonl").read_text().splitlines():
    print("ROW", line, flush=True)
print("E31DEDUP DONE", flush=True)
