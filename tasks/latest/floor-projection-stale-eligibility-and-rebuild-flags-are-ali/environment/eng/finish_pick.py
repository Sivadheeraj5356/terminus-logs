from __future__ import annotations


def latest_finish(events: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    out: dict[str, dict[str, object]] = {}
    for event in sorted(events, key=lambda row: int(row["seq"]), reverse=True):
        if event["kind"] != "finish":
            continue
        node = str(event["node"])
        if node not in out:
            out[node] = event
    return out
