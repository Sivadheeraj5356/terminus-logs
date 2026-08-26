#!/bin/bash
set -euo pipefail

cd /app

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

python3 <<'PY'
from pathlib import Path

require = lambda p, f: f in Path(p).read_text(encoding="utf-8") or (_ for _ in ()).throw(
    SystemExit(f"expected {f!r} in {p}")
)
require("/app/eng/ledger_lane.py", ">= int(floor)")
require("/app/eng/gen_slice.py", '"generation_floor" in entry')
require("/app/eng/gen_slice.py", "return int(resolved_floor)")
require("/app/eng/catalog.py", 'row["generation_floor"] = int(item["generation_floor"])')
require("/app/eng/settings.py", 'key == "generation_floor"')
require("/app/eng/run.py", "filter_generation(kept, filter_floor)")
require("/app/eng/run.py", "projection_floor(floor, runtime_floor)")
settings = Path("/app/eng/settings.py").read_text(encoding="utf-8")
if "_CFG_CACHE" in settings:
    raise SystemExit("settings.py still caches lineage config")
catalog = Path("/app/eng/catalog.py").read_text(encoding="utf-8")
if "gen_floor_override" in catalog:
    raise SystemExit("catalog.py still emits gen_floor_override alias")
gen_slice = Path("/app/eng/gen_slice.py").read_text(encoding="utf-8")
if "gen_floor_override" in gen_slice or "if val:" in gen_slice:
    raise SystemExit("gen_slice.py still uses override alias or truthiness")

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
PY

find /app/eng -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true

bash /app/scripts/frontier.sh
