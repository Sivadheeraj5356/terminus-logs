#!/usr/bin/env bash
set -euo pipefail

APP_ROOT="${APP_ROOT:-/app}"
LOCK_PATH="${1:-/app/config/hf-assets.lock.json}"
MIRROR_ROOT="${HF_MIRROR_ROOT:-/data/hf-mirror}"
TRANSCRIPT="${HF_TRANSCRIPT:-/app/docs/release-council-transcript.md}"
TARGET_ROUTE="${TARGET_ROUTE:-public-synonym}"
REPO="HuggingFaceFW/fineweb-edu-score-2"

cd "$APP_ROOT"
export TARGET_ROUTE APP_ROOT MIRROR_ROOT TRANSCRIPT

PYTHONPATH=kit python3 - <<'PY' "$LOCK_PATH"
import json
import os
import re
import sys
from pathlib import Path

from n7 import gradle_lock_digest, metadata_digest

lock_path = Path(sys.argv[1])
lock = json.loads(lock_path.read_text(encoding="utf-8"))
mirror_root = Path(os.environ.get("HF_MIRROR_ROOT", "/data/hf-mirror"))
transcript = Path(os.environ.get("HF_TRANSCRIPT", "/app/docs/release-council-transcript.md"))
target_route = os.environ.get("TARGET_ROUTE", "public-synonym")
repo = "HuggingFaceFW/fineweb-edu-score-2"

text = transcript.read_text(encoding="utf-8")
revision = lock.get("revision")
files = set()
forbidden = set()
for match in re.finditer(r"<!--\s*FINAL_RATIFIED:([^>]+)-->", text):
    parts = dict(p.split("=", 1) for p in match.group(1).strip().split() if "=" in p)
    if parts.get("route") != target_route:
        continue
    if "revision" in parts:
        revision = parts["revision"]
    if "files" in parts:
        files.update(parts["files"].split(","))

if lock.get("repository") != repo:
    raise SystemExit("repository mismatch")
if lock.get("revision") != revision:
    raise SystemExit("revision mismatch")

meta_path = mirror_root / repo / "fineweb-edu-score-2" / "revisions" / revision / "metadata.json"
meta_digest = metadata_digest(meta_path)
if lock.get("source_metadata_digest") != meta_digest:
    raise SystemExit("metadata digest mismatch")

gradle_digest = gradle_lock_digest()
if lock.get("gradle_lock_digest") != gradle_digest:
    raise SystemExit("gradle digest mismatch")

route = next((r for r in lock.get("routes", []) if r.get("route_id") == target_route), None)
if route is None:
    raise SystemExit("missing route")
paths = {entry["path"] for entry in route.get("files", [])}
if not files.issubset(paths):
    raise SystemExit("missing required file")
PY
