#!/usr/bin/env python
"""Verify that an atlas_optimizer output directory is internally consistent: the
request count and byte total in report.json must equal the files actually emitted.

This is the end-to-end accounting invariant for the deployable artifact. A byte-bundle
is one self-describing .bin per chunk (a 4-byte header length, a JSON offset index, then
the payloads); this checker confirms every .bin is well-formed and that no reported byte
or request is hidden.

Usage: python verify_output.py OUT_DIR
"""
import json
import struct
import sys
from pathlib import Path


def main(out):
    out = Path(out)
    report = json.load((out / "report.json").open())
    META = {"report.json", "atlas.css", "usage.html"}
    # every emitted resource EXCEPT the metadata files is a served image (atlas/strip
    # .webp, byte-bundle .bin, or an individual .webp)
    emitted = {p.name: p.stat().st_size for p in out.iterdir()
               if p.is_file() and p.name not in META}
    stray_json = [p.name for p in out.iterdir()
                  if p.suffix == ".json" and p.name != "report.json"]
    total_reported = sum(g["bytes_out"] for g in report["groups"])
    req_reported = sum(g["requests"] for g in report["groups"])
    total_actual = sum(emitted.values())
    req_actual = len(emitted)

    ok = True
    def check(name, cond):
        nonlocal ok
        print(("PASS " if cond else "FAIL ") + name)
        ok = ok and cond

    check(f"bytes: report {total_reported:,} == emitted {total_actual:,}",
          total_reported == total_actual)
    check(f"requests: report {req_reported} == emitted files {req_actual}",
          req_reported == req_actual)
    check(f"no stray .json index files ({stray_json})", not stray_json)

    # every byte-bundle .bin is well-formed and self-contained
    for p in out.glob("bundle_*.bin"):
        b = p.read_bytes()
        hlen = struct.unpack(">I", b[:4])[0]
        idx = json.loads(b[4:4 + hlen].decode())
        payloads = sum(l for _, l in idx.values())
        check(f"{p.name}: size == 4 + header + payloads",
              len(b) == 4 + hlen + payloads)

    print("OK" if ok else "INVARIANT VIOLATED")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else ".")
