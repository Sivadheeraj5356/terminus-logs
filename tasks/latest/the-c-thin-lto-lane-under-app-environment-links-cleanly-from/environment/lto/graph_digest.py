"""Compute import-hash inputs for thin summary modules."""

from __future__ import annotations

import hashlib
from pathlib import Path

from lto.module_index import source_name
from lto import transitive_closure


def _digest(paths: list[Path]) -> str:
    hasher = hashlib.sha256()
    for path in sorted(paths, key=lambda p: str(p)):
        hasher.update(path.name.encode())
        hasher.update(path.read_bytes())
    return hasher.hexdigest()


def input_paths(module: str, src_root: Path, work_root: Path) -> list[Path]:
    if module == "gate_abi":
        paths = [work_root / "gen" / "gate_abi.cpp", work_root / "gen" / "gate_abi.h"]
    else:
        paths = [src_root / source_name(module)]
    if module == "main":
        paths.extend(transitive_closure.resolve_paths(module, src_root, work_root))
    return paths


def import_hash(module: str, src_root: Path, work_root: Path) -> str:
    return _digest(input_paths(module, src_root, work_root))
