#!/bin/bash
set -euo pipefail

cd /app

python3 <<'PY'
from pathlib import Path

path = Path("/app/eng/dag.py")
text = path.read_text(encoding="utf-8")
text = text.replace(
    "return forward_topo(nodes, graph)",
    "return list(reversed(forward_topo(nodes, graph)))",
)
path.write_text(text, encoding="utf-8")
PY

cat > /app/eng/row_canon.py <<'PY'
from __future__ import annotations

import hashlib
import json

from .constants import DIGEST_ROW_KEYS
from .dag import reverse_topo


def frontier_digest_hex(
    stale_inputs: list[str],
    latest: dict[str, dict[str, object]],
    graph: dict[str, object],
) -> str:
    order = reverse_topo(stale_inputs, graph)
    lines: list[str] = []
    for node in order:
        if node not in latest:
            continue
        event = latest[node]
        payload = {
            "node": str(event["node"]),
            "hash": str(event["hash"]),
            "gen": int(event["gen"]),
            "seq": int(event["seq"]),
        }
        lines.append(
            json.dumps({key: payload[key] for key in DIGEST_ROW_KEYS}, separators=(",", ":"))
        )
    body = "\n".join(lines)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()
PY

cat > /app/eng/ledger.py <<'PY'
from __future__ import annotations

from pathlib import Path

from .io_util import read_jsonl


def load_ledger(path: str) -> list[dict[str, object]]:
    return read_jsonl(Path(path))


def filter_generation(events: list[dict[str, object]], floor: int) -> list[dict[str, object]]:
    return [event for event in events if int(event["gen"]) >= int(floor)]
PY

cat > /app/eng/ledger_lane.py <<'PY'
from __future__ import annotations


def filter_generation(events: list[dict[str, object]], floor: int) -> list[dict[str, object]]:
    return [event for event in events if int(event["gen"]) >= int(floor)]
PY

cat > /app/eng/gen_slice.py <<'PY'
from __future__ import annotations


def resolve_floor(entry: dict[str, object], runtime_floor: int) -> int:
    if "generation_floor" in entry:
        return int(entry["generation_floor"])
    return int(runtime_floor)


def projection_floor(resolved_floor: int, runtime_floor: int) -> int:
    return int(resolved_floor)
PY

cat > /app/eng/catalog.py <<'PY'
from __future__ import annotations


def normalize_consumer_row(item: dict[str, object]) -> dict[str, object]:
    row: dict[str, object] = {
        "id": str(item["id"]),
        "graph": str(item["graph"]),
        "ledger": str(item["ledger"]),
        "consumer": str(item["consumer"]),
    }
    if "generation_floor" in item:
        row["generation_floor"] = int(item["generation_floor"])
    return row
PY

cat > /app/eng/settings.py <<'PY'
from __future__ import annotations

from pathlib import Path


def load_lineage_cfg(path: Path) -> tuple[int, bool]:
    generation_floor = 1
    fan_in_require_all = True
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key == "generation_floor":
            generation_floor = int(value)
        elif key == "fan_in_require_all":
            fan_in_require_all = value.lower() == "true"
    return generation_floor, fan_in_require_all
PY

cat > /app/eng/registry.py <<'PY'
from __future__ import annotations


def latest_finish(events: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    out: dict[str, dict[str, object]] = {}
    for event in sorted(events, key=lambda row: int(row["seq"])):
        if event["kind"] != "finish":
            continue
        out[str(event["node"])] = event
    return out
PY

cat > /app/eng/gates.py <<'PY'
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
    return int(latest[watch]["rows"]) >= min_rows
PY

cat > /app/eng/subscribe.py <<'PY'
from __future__ import annotations

from .gates import gate_active


def _parents_ready(
    graph: dict[str, object],
    node: str,
    latest: dict[str, dict[str, object]],
) -> bool:
    table = graph.get("nodes", {})
    entry = table.get(node)
    if not isinstance(entry, dict):
        return True
    deps = entry.get("depends", [])
    if not deps:
        return True
    return all(str(dep) in latest for dep in deps)


def stale_inputs(
    graph: dict[str, object],
    consumer: dict[str, object],
    latest: dict[str, dict[str, object]],
    fan_in_require_all: bool,
) -> list[str]:
    out: list[str] = []
    last_materialized = consumer["last_materialized"]
    for node in consumer["subscribes"]:
        node_s = str(node)
        if fan_in_require_all and not _parents_ready(graph, node_s, latest):
            continue
        if not gate_active(graph, node_s, latest):
            continue
        if node_s not in latest:
            out.append(node_s)
            continue
        current = str(latest[node_s]["hash"])
        prior = str(last_materialized.get(node_s, ""))
        if current != prior:
            out.append(node_s)
    return sorted(out)


def rebuild_required(stale: list[str]) -> bool:
    return len(stale) > 0
PY

cat > /app/eng/pack_audit.py <<'PY'
from __future__ import annotations

from .row_canon import frontier_digest_hex
from .subscribe import rebuild_required, stale_inputs


def audit_consumer(
    graph: dict[str, object],
    consumer: dict[str, object],
    latest: dict[str, dict[str, object]],
    fan_in_require_all: bool,
) -> dict[str, object]:
    stale = stale_inputs(graph, consumer, latest, fan_in_require_all)
    return {
        "stale_inputs": stale,
        "rebuild_required": rebuild_required(stale),
        "frontier_digest_hex": frontier_digest_hex(stale, latest, graph),
    }
PY

python3 <<'PY'
from pathlib import Path

def require(path: str, fragment: str) -> None:
    if fragment not in Path(path).read_text(encoding="utf-8"):
        raise SystemExit(f"expected {fragment!r} in {path}")

require("/app/eng/dag.py", "reversed(forward_topo")
require("/app/eng/row_canon.py", "reverse_topo")
frontier_src = Path("/app/eng/row_canon.py").read_text(encoding="utf-8")
if "sort_keys=True" in frontier_src:
    raise SystemExit("row_canon.py must not reorder digest JSON keys")
if "sorted(stale_inputs)" in frontier_src:
    raise SystemExit("row_canon.py still digests alphabetical stale order")
if 'join(lines) + "\\n"' in frontier_src or "join(lines) + '\\n'" in frontier_src:
    raise SystemExit("row_canon.py still appends trailing newline after final row")
settings = Path("/app/eng/settings.py").read_text(encoding="utf-8")
if "_CFG_CACHE" in settings:
    raise SystemExit("settings.py still caches lineage config")
gen_slice = Path("/app/eng/gen_slice.py").read_text(encoding="utf-8")
if "gen_floor_override" in gen_slice or "if val:" in gen_slice:
    raise SystemExit("gen_slice.py still uses override alias or truthiness")
require("/app/eng/ledger.py", ">= int(floor)")
require("/app/eng/ledger_lane.py", ">= int(floor)")
require("/app/eng/gen_slice.py", '"generation_floor" in entry')
require("/app/eng/gen_slice.py", "return int(resolved_floor)")
require("/app/eng/catalog.py", 'row["generation_floor"] = int(item["generation_floor"])')
require("/app/eng/settings.py", 'key == "generation_floor"')
require("/app/eng/run.py", "filter_generation(kept, filter_floor)")
require("/app/eng/run.py", "projection_floor(floor, runtime_floor)")
require("/app/eng/registry.py", 'sorted(events, key=lambda row: int(row["seq"])')
require("/app/eng/gates.py", ">= min_rows")
require("/app/eng/subscribe.py", "len(stale) > 0")
require("/app/eng/subscribe.py", "_parents_ready")
require("/app/eng/subscribe.py", "fan_in_require_all")
require("/app/eng/pack_audit.py", "fan_in_require_all")
catalog = Path("/app/eng/catalog.py").read_text(encoding="utf-8")
if "gen_floor_override" in catalog:
    raise SystemExit("catalog.py still emits gen_floor_override alias")
pack = Path("/app/eng/pack_audit.py").read_text(encoding="utf-8")
if "feed_frontier" in pack:
    raise SystemExit("pack_audit still routes digest through feed_frontier")
if "span_digest" in pack:
    raise SystemExit("pack_audit still routes digest through span_digest")
if "row_canon" not in pack:
    raise SystemExit("pack_audit must route digest through row_canon")
if "_EMPTY" in pack or "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855" in pack:
    raise SystemExit("pack_audit must derive rebuild_required from the stale set, not digest emptiness")
if "rebuild_required(stale)" not in pack:
    raise SystemExit("pack_audit must call rebuild_required on the stale set")
Path("/app/eng/manifest.py").write_text(
    '''from __future__ import annotations

import json
from pathlib import Path

from .catalog import normalize_consumer_row


def load_manifest(path: Path) -> list[dict[str, object]]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    return [normalize_consumer_row(item) for item in doc.get("consumers", [])]
''',
    encoding="utf-8",
)
manifest = Path("/app/eng/manifest.py").read_text(encoding="utf-8")
if "_MANIFEST_CACHE" in manifest:
    raise SystemExit("manifest.py still caches manifest.json")
feed = Path("/app/eng/feed_frontier.py").read_text(encoding="utf-8")
if "reverse_topo" not in feed:
    raise SystemExit("feed_frontier honeypot lost reverse_topo wiring")
if "sorted(reverse_topo" not in feed:
    raise SystemExit("feed_frontier honeypot lost alphabetical re-sort after reverse_topo")
span = Path("/app/eng/span_digest.py").read_text(encoding="utf-8")
if "sort_keys=True" not in span:
    raise SystemExit("span_digest off-path decoy was altered")
if "reverse_topo" not in span:
    raise SystemExit("span_digest honeypot lost reverse_topo wiring")
PY

find /app/eng -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true

bash /app/scripts/frontier.sh
