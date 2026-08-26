#!/bin/bash
set -euo pipefail

PROFILE="${1:-alpha}"
export PATH="/usr/local/go/bin:/usr/local/bin:${PATH}"

ROOT="/app/var/state"
OUT="/app/output"
TOPO="/app/data/topology_w3"
FEED="/app/var/grant_feed.jsonl"
FOREIGN="${TOPO}/foreign_rows.json"

mkdir -p /app/bin /app/output /app/var "${ROOT}"

cd /app/environment
go build -o /app/bin/linkctl ./cmd/linkctl

rm -rf "${OUT}"/* "${ROOT}"
mkdir -p "${OUT}" "${ROOT}"

/app/bin/linkctl boot --profile "${PROFILE}" --root "${ROOT}" --out "${OUT}"
/app/bin/linkctl reconfigure --profile "${PROFILE}" --root "${ROOT}" --out "${OUT}"
/app/bin/linkctl reconfigure --profile "beta" --root "${ROOT}" --out "${OUT}"
