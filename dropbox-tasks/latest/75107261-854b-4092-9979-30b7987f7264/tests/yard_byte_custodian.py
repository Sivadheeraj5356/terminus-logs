"""Snapshot and compare yard bytes/modes/symlinks for mutation custody."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path


def snapshot(root: Path) -> dict[str, tuple]:
    out = {}
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames.sort()
        filenames.sort()
        base = Path(dirpath)
        rel_dir = base.relative_to(root).as_posix()
        if rel_dir == ".":
            rel_dir = ""
        for name in sorted(dirnames):
            p = base / name
            rel = f"{rel_dir}/{name}".lstrip("/")
            if p.is_symlink():
                out[rel] = ("symlink", os.readlink(p), oct(p.lstat().st_mode & 0o777))
            else:
                out[rel] = ("dir", "", oct(p.stat().st_mode & 0o777))
        for name in filenames:
            p = base / name
            rel = f"{rel_dir}/{name}".lstrip("/")
            if p.is_symlink():
                out[rel] = ("symlink", os.readlink(p), oct(p.lstat().st_mode & 0o777))
            else:
                data = p.read_bytes()
                out[rel] = ("file", hashlib.sha256(data).hexdigest(), oct(p.stat().st_mode & 0o777))
    return out


def equal(a: dict, b: dict) -> bool:
    return a == b
