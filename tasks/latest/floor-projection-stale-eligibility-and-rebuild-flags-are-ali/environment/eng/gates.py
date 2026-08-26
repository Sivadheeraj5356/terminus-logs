from __future__ import annotations


def gate_active(
    graph: dict[str, object],
    node: str,
    latest: dict[str, dict[str, object]],
) -> bool:
    gates = graph.get("gates", {})
    if node not in gates:
        return True
    gate = gates[node]
    watch = str(gate["watch"])
    min_rows = int(gate["min_rows"])
    if watch not in latest:
        return False
    return int(latest[watch]["rows"]) > min_rows
