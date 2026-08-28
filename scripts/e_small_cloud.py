"""Modal-side wrapper: static compression study for small photo thumbnails (112/56px)."""
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, "/app")
try:
    import pillow_avif  # noqa: F401
except ImportError:
    pass

zipfile.ZipFile("/app/assets_bundle.zip").extractall("/assets")

import static_study  # noqa: E402

sys.argv = ["static_study.py", "--tag", "phase1_smallthumbs",
            "--classes", "photos112,photos56",
            "--counts", "10,50,200,500",
            "--codecs", "png,webp_ll,jpeg:30,jpeg:50,jpeg:65,jpeg:80,jpeg:90,"
            "webp:30,webp:50,webp:65,webp:80,webp:90",
            "--paddings", "0,8"]
static_study.main()

for line in Path("/results/static/phase1_smallthumbs/results.jsonl").read_text().splitlines():
    print("ROW", line, flush=True)
print("SMALLTHUMBS DONE", flush=True)
