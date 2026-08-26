from __future__ import annotations

from typing import Any


def _canonical_id(panel_id: str, panels: dict[str, Any]) -> str | None:
    row = panels.get(panel_id)
    if row is None:
        return None
    alias = row.get("alias_of")
    if alias:
        return str(alias)
    return panel_id


def bundle_is_valid(bundle: dict[str, Any], catalogs: dict[str, Any]) -> bool:
    panels = catalogs["panels"]
    pattern_anchors = catalogs["pattern_anchors"]
    for entry in bundle["panels"]:
        iid = entry["panel_id"]
        canonical = _canonical_id(iid, panels)
        if canonical is None or canonical not in panels:
            return False
        if canonical not in pattern_anchors:
            return False
    return True
