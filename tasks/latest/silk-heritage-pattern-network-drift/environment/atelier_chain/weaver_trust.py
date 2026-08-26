from __future__ import annotations

from typing import Any


def walk_weaver_trust(
    weaver_id: str,
    lineage_map: dict[str, str],
    master_weavers: dict[str, Any],
) -> float:
    profile = master_weavers.get(weaver_id, {})
    return float(profile.get("base_trust", 1.0))
