from __future__ import annotations

from .gates import gate_active


def stale_inputs(
    graph: dict[str, object],
    consumer: dict[str, object],
    latest: dict[str, dict[str, object]],
    fan_in_require_all: bool = True,
) -> list[str]:
    _ = fan_in_require_all
    out: list[str] = []
    last_materialized = consumer["last_materialized"]
    for node in consumer["subscribes"]:
        if not gate_active(graph, str(node), latest):
            continue
        if str(node) not in latest:
            out.append(str(node))
            continue
        current = str(latest[str(node)]["hash"])
        prior = str(last_materialized.get(str(node), ""))
        if current != prior:
            out.append(str(node))
    return sorted(out)


def rebuild_required(stale: list[str]) -> bool:
    return len(stale) == 0
