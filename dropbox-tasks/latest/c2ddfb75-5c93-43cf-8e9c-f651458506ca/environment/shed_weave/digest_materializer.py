from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from shed_weave.loader import load_registry


def merge_dye_overlays(
    dye_reformulations: dict[str, Any],
    data_root: Path,
) -> dict[str, Any]:
    overlay_dir = data_root / "dye_reformulations" / "overrides"
    if not overlay_dir.is_dir():
        return dye_reformulations
    merged = {key: list(rows) for key, rows in dye_reformulations.items()}
    for path in sorted(overlay_dir.glob("*.json")):
        overlay = json.loads(path.read_text())
        for panel_id, rows in overlay.items():
            merged.setdefault(panel_id, [])
            merged[panel_id] = list(merged[panel_id]) + list(rows)
    return merged


def build_catalog_snapshot(data_root: Path, *, include_overlays: bool = False) -> dict[str, Any]:
    dye_reformulations = load_registry(data_root / "dye_reformulations")
    if include_overlays:
        dye_reformulations = merge_dye_overlays(dye_reformulations, data_root)
    return {
        "master_weavers": load_registry(data_root / "master_weavers"),
        "dye_reformulations": dye_reformulations,
        "export_routes": load_registry(data_root / "export_routes"),
        "loom_letters": load_registry(data_root / "loom_letters"),
        "pattern_anchors": load_registry(data_root / "pattern_anchors"),
        "panels": load_registry(data_root / "panels"),
        "merchant_transfers": load_registry(data_root / "merchant_transfers"),
        "school_recitals": load_registry(data_root / "school_recitals"),
    }


def registry_digest(catalogs: dict[str, Any]) -> str:
    payload = json.dumps(
        catalogs,
        sort_keys=True,
        default=str,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:16]
