"""Resolve header include closure for import-sensitive translation units."""

from __future__ import annotations

from pathlib import Path

# Logical include edges from primary sources to generated or shared headers.
_HEADER_CLOSURE: dict[str, tuple[str, ...]] = {
    "anchor": (),
    "dispatch": ("gate_abi.h",),
    "consumer": ("gate_abi.h",),
    "main": ("gate_abi.h", "dispatch.h", "consumer.h", "anchor.h"),
    "gate_abi": ("gate_abi.h",),
}


def header_names(module: str) -> tuple[str, ...]:
    return _HEADER_CLOSURE.get(module, ())


def resolve_paths(module: str, src_root: Path, work_root: Path) -> list[Path]:
    """Map include closure names to on-disk paths under src or generated roots."""
    paths: list[Path] = []
    gen_root = work_root / "gen"
    for name in header_names(module):
        if name == "gate_abi.h":
            candidate = gen_root / "gate_abi.h"
        else:
            candidate = src_root / name
        if candidate.is_file():
            paths.append(candidate)
    return paths
