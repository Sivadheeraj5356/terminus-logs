from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_json(path: Path) -> Any:
    return json.loads(path.read_text())


def load_registry(directory: Path) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for path in sorted(directory.glob("*.json")):
        payload = load_json(path)
        merged.update(payload)
    return merged


def data_root() -> Path:
    return Path("/app/data")
