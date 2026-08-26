"""Lot evidence dossier ingestion."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_metadata(directory: str | Path) -> dict[str, Any]:
    root = Path(directory)
    batch = _read_json(root / "batch.json")
    policy = _read_json(root / "batch_policy.json")
    if batch["batch_id"] != policy["batch_id"]:
        raise ValueError("batch_id mismatch between batch.json and batch_policy.json")
    return {
        "batch": batch,
        "policy": policy,
        "qc_records": _read_json(root / "qc_records.json"),
        "equipment": _read_json(root / "equipment_status.json"),
        "environmental": _read_json(root / "environmental_logs.json"),
        "documentation": _read_json(root / "documentation_manifest.json"),
    }
