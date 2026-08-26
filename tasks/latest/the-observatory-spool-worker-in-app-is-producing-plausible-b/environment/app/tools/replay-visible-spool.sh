#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export SPECZ_APP="${SPECZ_APP:-$ROOT}"
"$ROOT/tools/reset-visible-spool.sh"
echo "--- worker lifecycle ---"
"$ROOT/bin/specz-worker" --once || true
echo "--- drift.jsonl ---"
if [[ -f /output/drift.jsonl ]]; then cat /output/drift.jsonl; else echo "(no output)"; fi
