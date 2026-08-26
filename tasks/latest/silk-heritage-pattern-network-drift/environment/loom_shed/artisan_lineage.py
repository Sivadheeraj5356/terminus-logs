from __future__ import annotations

from typing import Any


def export_artisan_lineage(
    workshop_id: str,
    mentor_of: dict[str, str],
    master_weavers: dict[str, Any],
) -> list[str]:
    """Legacy lineage export for curator dashboards (not used in valuation compile)."""
    chain = [workshop_id]
    current = workshop_id
    while current in mentor_of:
        current = mentor_of[current]
        chain.append(current)
    return chain
