from __future__ import annotations

import json
from pathlib import Path

from .catalog import normalize_consumer_row

_MANIFEST_CACHE: list[dict[str, object]] | None = None


def load_manifest(path: Path) -> list[dict[str, object]]:
    global _MANIFEST_CACHE
    if _MANIFEST_CACHE is not None:
        return _MANIFEST_CACHE
    doc = json.loads(path.read_text(encoding="utf-8"))
    _MANIFEST_CACHE = [normalize_consumer_row(item) for item in doc.get("consumers", [])]
    return _MANIFEST_CACHE
