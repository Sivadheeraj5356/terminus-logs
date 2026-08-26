from __future__ import annotations

from typing import Any


def compile_lineage_map(
    mentor_of: dict[str, str],
    lineage_epochs: dict[str, Any],
    completion_year: int,
) -> dict[str, str]:
    compiled: dict[str, str] = {}
    for child, parent in mentor_of.items():
        epoch = lineage_epochs.get(child, {})
        active_from = int(epoch.get("active_from_year", 0))
        if completion_year > active_from:
            compiled[child] = parent
    return compiled
