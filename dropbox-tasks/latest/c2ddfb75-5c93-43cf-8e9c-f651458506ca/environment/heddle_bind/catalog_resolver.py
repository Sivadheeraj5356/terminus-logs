from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PanelEntry:
    panel_id: str
    canonical_id: str
    weaver_id: str
    completion_year: int


def resolve_panel_entry(panel_id: str, catalog: dict[str, Any]) -> PanelEntry:
    row = catalog[panel_id]
    if "alias_of" in row:
        canonical = str(row["alias_of"])
    else:
        canonical = panel_id
    return PanelEntry(
        panel_id=panel_id,
        canonical_id=panel_id,
        weaver_id=str(row.get("weaver_id", catalog.get(canonical, row)["weaver_id"])),
        completion_year=int(
            row.get("completion_year", catalog.get(canonical, {}).get("completion_year", 1900))
        ),
    )
