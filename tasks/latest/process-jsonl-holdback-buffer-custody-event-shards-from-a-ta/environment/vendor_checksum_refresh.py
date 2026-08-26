#!/usr/bin/env python3
import hashlib
import json
import os
from pathlib import Path

vendor = Path(os.environ.get("VENDOR_DIR", "/usr/local/cargo/vendor"))


def package_digest(files: dict[str, str]) -> str:
    return hashlib.sha256("".join(sorted(files.values())).encode()).hexdigest()


for crate in vendor.iterdir():
    if not crate.is_dir():
        continue
    checksum_path = crate / ".cargo-checksum.json"
    package = None
    if checksum_path.is_file():
        old = json.loads(checksum_path.read_text(encoding="utf-8"))
        package = old.get("package")
    files = {
        path.relative_to(crate).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(crate.rglob("*"))
        if path.is_file() and path.name != ".cargo-checksum.json"
    }
    if package is None:
        package = package_digest(files)
    checksum_path.write_text(
        json.dumps({"files": files, "package": package}, separators=(",", ":")),
        encoding="utf-8",
    )
