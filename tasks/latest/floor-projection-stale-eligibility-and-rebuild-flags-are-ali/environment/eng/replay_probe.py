from __future__ import annotations


def probe_tick_order(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    return sorted(rows, key=lambda row: (str(row.get("lane", "")), int(row.get("tick", 0))))
