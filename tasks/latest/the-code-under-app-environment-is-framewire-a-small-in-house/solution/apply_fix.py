#!/usr/bin/env python3
import shutil
from pathlib import Path

FIXED = Path("/solution/fixed")
DEST = Path("/app/environment/internal/proto")

FILES = [
    "query.go",
    "bind.go",
    "copy_data.go",
    "framing.go",
    "frontend.go",
    "function_call.go",
    "batch.go",
    "format_codes.go",
]


def main():
    for name in FILES:
        src = FIXED / name
        dst = DEST / name
        assert src.exists(), f"missing fixed source: {src}"
        assert dst.exists(), f"target not present: {dst}"
        shutil.copyfile(src, dst)


if __name__ == "__main__":
    main()
