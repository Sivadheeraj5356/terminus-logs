from __future__ import annotations

import json
from pathlib import Path

from .constants import OUTPUT
from .gen_slice import projection_floor, resolve_floor
from .graph import load_consumer, load_graph
from .ledger import load_ledger
from .ledger_lane import filter_generation
from .manifest import load_manifest
from .registry import latest_finish
from .pack_audit import audit_consumer
from .settings import load_lineage_cfg


def build_report() -> dict[str, object]:
    manifest = load_manifest(Path("/app/data/manifest.json"))
    runtime_floor, fan_in = load_lineage_cfg(Path("/app/cfg/lineage.toml"))
    schema_mark = int(Path("/app/stubs/schema_level.txt").read_text(encoding="utf-8").strip())
    consumers: dict[str, dict[str, object]] = {}
    for entry in manifest:
        graph = load_graph(str(entry["graph"]))
        ledger = load_ledger(str(entry["ledger"]))
        consumer = load_consumer(str(entry["consumer"]))
        floor = resolve_floor(entry, runtime_floor)
        filter_floor = projection_floor(floor, runtime_floor)
        kept = [event for event in ledger if event["kind"] == "finish"]
        kept = filter_generation(kept, filter_floor)
        latest = latest_finish(kept)
        consumers[str(entry["id"])] = audit_consumer(graph, consumer, latest, fan_in)
    return {"schema_mark": schema_mark, "consumers": consumers}


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    report = build_report()
    OUTPUT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
