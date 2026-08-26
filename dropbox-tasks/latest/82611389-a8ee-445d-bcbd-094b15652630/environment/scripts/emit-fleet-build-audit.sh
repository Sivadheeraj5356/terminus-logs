#!/usr/bin/env bash
set -euo pipefail

# Baseline stub: incomplete build-train driver. Agents must implement probes,
# secure policy rewrite, probe snapshot under FLEET_STAGE_ROOT, and compliance export.
API_BASE="${API_BASE:-http://127.0.0.1:8080}"
RELEASE_PIN="/app/fixtures/fleet-release.pin"
POLICY_FILE="${POLICY_PATH:-/app/config/fleet-policy.toml}"
REPORT_FILE="/app/output/fleet-build-compliance.json"
REGISTRY_DB="${REGISTRY_DB_PATH:-/app/data/module-registry.json}"
FLEET_STAGE_ROOT="${FLEET_STAGE_ROOT:-/app/var/fleet-stage}"

log() { echo "[fleet-build-audit] $*" >&2; }

wait_for_api() {
  for _ in $(seq 1 30); do
    code=$(curl -s -o /dev/null -w '%{http_code}' "${API_BASE}/health" || true)
    if [[ "${code}" == "200" ]]; then
      return 0
    fi
    sleep 0.2
  done
  log "api not reachable"
  return 1
}

read_release_pin() {
  head -n 1 "${RELEASE_PIN}"
}

approved_count() {
  python3 - "${REGISTRY_DB}" <<'PY'
import json, sys
path = sys.argv[1]
rows = json.load(open(path, encoding="utf-8"))
print(sum(1 for r in rows if r.get("status") == "approved"))
PY
}

write_policy() {
  local pin="$1"
  cat > "${POLICY_FILE}" <<EOF
require_registry_approval = false
debug_endpoints_enabled = true
min_module_versions = billing-api:1.0.0,ingest-worker:1.0.0
fleet_release_pin = ${pin}
EOF
}

policy_digest() {
  sha256sum "${POLICY_FILE}" | awk '{print $1}'
}

write_report() {
  local count="$1"
  mkdir -p "$(dirname "${REPORT_FILE}")" "${FLEET_STAGE_ROOT}"
  cat > "${REPORT_FILE}" <<JSON
{
  "policy_applied": false,
  "openapi_valid": false,
  "release_pin_valid": false,
  "debug_endpoint_blocked": false,
  "build_plan_valid": false,
  "approved_module_count": ${count},
  "policy_digest": "$(policy_digest)"
}
JSON
}

main() {
  log "waiting for api"
  wait_for_api

  local pin count
  pin="$(read_release_pin)"
  count="$(approved_count)"
  write_policy "${pin}"
  write_report "${count}"
  log "report written (probe snapshot and live probes not implemented)"
}

main "$@"
