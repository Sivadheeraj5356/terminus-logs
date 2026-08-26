"""Checkpoint persistence for sandbox recovery replay."""
# ruff: noqa: F841, F401

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from lib.access import cap_remaining


def checkpoint_path(root: Path) -> Path:
    return root / "checkpoint.json"


def save_checkpoint(
    root: Path,
    generation: int,
    fuel: dict[str, int],
    caps: dict[str, dict],
    host_calls: list[dict],
    fuel_used: int,
) -> dict[str, Any]:
    root.mkdir(parents=True, exist_ok=True)
    snap_caps: dict[str, dict] = {}
    for cid, cap in caps.items():
        snap_caps[cid] = {
            "ops": list(cap.get("ops", [])),
            "baseline_ops": list(cap.get("baseline_ops", [])),
            "uses_left": cap_remaining(cap),
        }
    doc = {
        "generation": generation,
        "fuel_remaining": fuel.get("remaining", 0) + fuel_used,
        "fuel_used": fuel_used,
        "caps": snap_caps,
        "host_calls": list(host_calls),
    }
    checkpoint_path(root).write_text(json.dumps(doc, sort_keys=True) + "\n")
    return doc


def load_checkpoint(root: Path) -> dict[str, Any]:
    path = checkpoint_path(root)
    if not path.is_file():
        return {}
    return json.loads(path.read_text())


def spent_uses(snapshot_uses: int, current_uses: int) -> int:
    return max(0, int(snapshot_uses) - int(current_uses))
