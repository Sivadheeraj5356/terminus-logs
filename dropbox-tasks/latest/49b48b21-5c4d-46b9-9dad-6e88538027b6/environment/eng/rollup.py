from __future__ import annotations


def row_count_sum(events: list[dict[str, object]]) -> int:
    total = 0
    for event in events:
        if event["kind"] == "finish":
            total += int(event["rows"])
    return total
