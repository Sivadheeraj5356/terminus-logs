from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from heddle_bind.catalog_resolver import PanelEntry, resolve_panel_entry


@dataclass(frozen=True)
class PanelBundle:
    entry: PanelEntry
    dye_reformulations: list[dict[str, Any]]
    epochs: list[dict[str, Any]]
    loom_letters: list[dict[str, Any]]
    sales: list[dict[str, Any]]
    school_recitals: list[dict[str, Any]]
    base_appraisal: float


def materialize_panel_bundle(
    panel_id: str,
    catalogs: dict[str, Any],
) -> PanelBundle:
    entry = resolve_panel_entry(panel_id, catalogs["panels"])
    lookup_key = entry.panel_id
    canonical = entry.canonical_id
    return PanelBundle(
        entry=entry,
        dye_reformulations=list(catalogs["dye_reformulations"].get(lookup_key, [])),
        epochs=list(catalogs["export_routes"].get(lookup_key, [])),
        loom_letters=list(catalogs["loom_letters"].get(canonical, [])),
        sales=list(catalogs.get("merchant_transfers", {}).get(canonical, [])),
        school_recitals=list(catalogs["school_recitals"].get(lookup_key, [])),
        base_appraisal=float(catalogs["pattern_anchors"][canonical]["base_appraisal"]),
    )
