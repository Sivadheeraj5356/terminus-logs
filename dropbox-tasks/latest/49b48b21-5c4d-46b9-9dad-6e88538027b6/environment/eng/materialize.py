from __future__ import annotations

from pathlib import Path


def load_lineage_cfg(path: Path) -> tuple[int, bool]:
    _ = path
    return 1, True


def normalize_consumer_row(item: dict[str, object]) -> dict[str, object]:
    row: dict[str, object] = {
        "id": str(item["id"]),
        "graph": str(item["graph"]),
        "ledger": str(item["ledger"]),
        "consumer": str(item["consumer"]),
    }
    if item.get("generation_floor"):
        row["generation_floor"] = int(item["generation_floor"])
    return row


def filter_generation(events: list[dict[str, object]], floor: int) -> list[dict[str, object]]:
    return [event for event in events if int(event["gen"]) > int(floor)]
