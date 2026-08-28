"""Modal-side wrapper for E3.1: unzip assets, run the ordering study, emit rows.

Expects /app/assets_bundle.zip, /app/static_study.py, /app/e31_ordering.py.
Prints each result row prefixed with 'ROW ' for log-side collection.
"""
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, "/app")
try:
    import pillow_avif  # noqa: F401  (registers AVIF when Pillow lacks native support)
except ImportError:
    pass

zipfile.ZipFile("/app/assets_bundle.zip").extractall("/assets")
print("assets extracted:",
      len(list(Path("/assets/emoji").iterdir())),
      len(list(Path("/assets/photos").iterdir())), flush=True)

import e31_ordering  # noqa: E402

sys.argv = ["e31_ordering.py", "--tag", "e31_cloud",
            "--classes", "emoji,photos", "--n", "500",
            "--codecs", "avif:50,avif:80,webp:80,jpeg:80,jxl:80,png,webp_ll,jxl_ll"]
e31_ordering.main()

for line in Path("/results/static/e31_cloud/results.jsonl").read_text().splitlines():
    print("ROW", line, flush=True)
print("E31 DONE", flush=True)
