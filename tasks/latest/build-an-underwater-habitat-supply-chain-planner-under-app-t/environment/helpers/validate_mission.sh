#!/usr/bin/env bash
# Validates mission directory layout before ingest (diagnostic only).
set -euo pipefail
root="$1"
test -f "${root}/cargo.jsonl" && test -f "${root}/habitat.json"
