# atlas-optimizer

Turns a directory of small images into optimized web bundles by applying the decision
rules measured in the [ImageBundling study](https://apartsinprojects.github.io/ImageBundling/).

```bash
python atlas_optimizer.py INPUT_DIR --out OUT_DIR [--lossy-png] \
    [--manifest manifest.json] [--quality 80] [--chunks 4] \
    [--atlas-max-px 130] [--min-group 10]
```

What it does, in order:

1. **Folds exact duplicates**: pixel-identical files become one stored tile with many
   CSS entries (measured: repeat-heavy sets saved 16-21% from this step alone).
2. **Groups** by update cadence (from the manifest), lossless requirement, and tile
   dimensions, so a change invalidates only its own bundle.
3. **Chooses the bundle type per group** from the measured curves:
   - small lossy tiles (max side <= 130px): WebP **pixel atlas**, displayed via CSS
     `background-position` (saved 15-26% bytes at matched quality in the study, and
     2-9x time-to-all-visible on HTTP/1.1 and HTTP/3);
   - larger lossy tiles and all lossless tiles: **byte-bundle** (files concatenated
     into one self-describing `.bin`, a 4-byte header length plus a JSON offset index
     plus the payloads, decoded client-side via blob URLs), which collapses a chunk to
     one request at near-zero byte penalty (only the small offset header; pixel-atlasing
     these classes measured net-negative on bytes);
   - groups smaller than `--min-group`: individual files (bundling overhead not paid
     back).
4. **Chunks** each bundle (default 4): keeps nearly all savings, bounds cache
   invalidation and decoded-memory blast radius.

Outputs: `atlas_*.webp`, `bundle_*.bin` (self-describing, one request per chunk),
`atlas.css`
(`.ib-<name>` class per tile, duplicates aliased), `usage.html` (loader snippet),
`report.json` (per-group condition, bytes vs individual baseline, savings).

`manifest.json` (optional), per filename:
`{"hero.png": {"cadence": "weekly", "lossless": true}}`

Validation on the study's asset sets (verified against emitted bytes with
`verify_output.py`): 521 emoji (lossless PNG) -> 4 WebP-lossless strip-atlas chunks,
+5.1% vs individual PNGs (342 KB, the byte-optimal choice; with `--lossy-png` the same set
goes to 4 pixel-atlas chunks at +19.2% vs individual WebP); 521 photo thumbnails (119
exact duplicates folded) -> 4 self-describing byte-bundle chunks, +21.1% saved. Both
collapse 521 requests to 4.
