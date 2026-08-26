"""Restore state persistence helpers."""

from __future__ import annotations

import json
from pathlib import Path

from restore.constants import STATE_NAME


def load_previous_managed(root: Path) -> set[str]:
    state = root / STATE_NAME
    if not state.exists():
        return set()
    return set(json.loads(state.read_text()).get("managed", []))


def save_managed(root: Path, managed: set[str]) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / STATE_NAME).write_text(json.dumps({"managed": sorted(managed)}) + "\n")
