"""Read thin summary sidecars."""

from __future__ import annotations

import json
from pathlib import Path


def read_summary(path: Path) -> dict[str, object]:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def summary_hash_map(lto_root: Path, modules: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for module in modules:
        summary = read_summary(lto_root / f"{module}.summary.json")
        digest = summary.get("import_hash")
        if isinstance(digest, str):
            out[module] = digest
    return out
