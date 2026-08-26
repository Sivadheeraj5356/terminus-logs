from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_registry(directory: Path) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for path in sorted(directory.glob("*.json")):
        merged.update(json.loads(path.read_text()))
    return merged


def load_dye_reformulations(data_root: Path) -> dict[str, Any]:
    return load_registry(data_root / "dye_reformulations")
