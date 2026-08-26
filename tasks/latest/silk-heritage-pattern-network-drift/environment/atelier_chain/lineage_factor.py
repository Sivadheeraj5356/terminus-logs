from __future__ import annotations

from typing import Any


def walk_weaver_trust(
    workshop_id: str,
    successor_map: dict[str, str],
    master_weavers: dict[str, Any],
) -> float:
    profile = master_weavers.get(workshop_id, {})
    return float(profile.get("base_trust", 1.0))
