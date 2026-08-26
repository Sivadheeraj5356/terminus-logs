from __future__ import annotations


def normalize_consumer_row(item: dict[str, object]) -> dict[str, object]:
    row: dict[str, object] = {
        "id": str(item["id"]),
        "graph": str(item["graph"]),
        "ledger": str(item["ledger"]),
        "consumer": str(item["consumer"]),
    }
    if "generation_floor" in item:
        row["gen_floor_override"] = int(item["generation_floor"])
    return row
