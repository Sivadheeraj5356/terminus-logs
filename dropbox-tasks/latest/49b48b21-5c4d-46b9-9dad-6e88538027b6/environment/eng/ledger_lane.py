from __future__ import annotations


def filter_generation(events: list[dict[str, object]], floor: int) -> list[dict[str, object]]:
    cutoff = int(floor)
    return [event for event in events if int(event["gen"]) > cutoff]
