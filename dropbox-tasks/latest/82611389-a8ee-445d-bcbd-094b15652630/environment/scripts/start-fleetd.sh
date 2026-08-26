#!/usr/bin/env bash
set -euo pipefail

cd /app
export PATH="/usr/local/go/bin:${PATH}"
export REGISTRY_DB_PATH="${REGISTRY_DB_PATH:-/app/data/module-registry.json}"
export POLICY_PATH="${POLICY_PATH:-/app/config/fleet-policy.toml}"
export MANIFEST_PATH="${MANIFEST_PATH:-/app/data/module-manifest.csv}"
export LISTEN_ADDR="${LISTEN_ADDR:-127.0.0.1:8080}"

go build -o /app/bin/fleetd ./cmd/fleetd
exec /app/bin/fleetd
