#!/usr/bin/env bash
set -euo pipefail

API_BASE="${API_BASE:-http://127.0.0.1:8080}"
RELEASE_PIN="/app/fixtures/fleet-release.pin"
POLICY_FILE="${POLICY_PATH:-/app/config/fleet-policy.toml}"
REPORT_FILE="/app/output/fleet-build-compliance.json"
REGISTRY_DB="${REGISTRY_DB_PATH:-/app/data/module-registry.json}"
FLEET_STAGE_ROOT="${FLEET_STAGE_ROOT:-/app/var/fleet-stage}"
EXPECTED_ORDER='["auth-core","billing-api","ingest-worker","notify-hub","gateway"]'

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
  head -n 1 "${RELEASE_PIN}" | tr -d '\r\n'
}

approved_count() {
  python3 - "${REGISTRY_DB}" <<'PY'
import json, sys
path = sys.argv[1]
rows = json.load(open(path, encoding="utf-8"))
print(sum(1 for r in rows if r.get("status") == "approved"))
PY
}

probe_openapi() {
  local body
  body=$(curl -s "${API_BASE}/openapi.json")
  [[ "${body}" == *'"/v1/build-plan"'* && "${body}" == *'"/v1/build-attest"'* && "${body}" == *'"post"'* && "${body}" == *'"/health"'* ]]
}

probe_debug_endpoint() {
  curl -s -o /dev/null -w '%{http_code}' "${API_BASE}/debug/policy"
}

probe_build_plan() {
  curl -s -X POST -H 'Content-Type: application/json' -d '{}' "${API_BASE}/v1/build-plan"
}

probe_build_attest() {
  curl -s -X POST -H 'Content-Type: application/json' -d '{}' "${API_BASE}/v1/build-attest"
}

write_policy() {
  local pin="$1"
  cat > "${POLICY_FILE}" <<POLICY
require_registry_approval = true
debug_endpoints_enabled = false
min_module_versions = billing-api:2.0.0,ingest-worker:1.1.0
fleet_release_pin = ${pin}
POLICY
}

policy_digest() {
  sha256sum "${POLICY_FILE}" | awk '{print $1}'
}

write_snapshot() {
  local pin="$1"
  local openapi_ok="$2"
  local pin_ok="$3"
  local debug_ok="$4"
  local build_ok="$5"
  local attest_ok="$6"
  local plan_digest="$7"
  local plan_seal="$8"
  mkdir -p "${FLEET_STAGE_ROOT}"
  python3 - "${FLEET_STAGE_ROOT}/build-train-probe.json" "${API_BASE}" "${pin}" \
    "${openapi_ok}" "${pin_ok}" "${debug_ok}" "${build_ok}" "${attest_ok}" \
    "${plan_digest}" "${plan_seal}" <<'PY2'
import json, sys
path, api_base, pin, o, p, d, b, a, digest, seal = sys.argv[1:11]
doc = {
  "api_base": api_base,
  "plan_digest": digest,
  "plan_seal": seal,
  "probes": {
    "build_attest_valid": a == "true",
    "build_plan_valid": b == "true",
    "debug_endpoint_blocked": d == "true",
    "openapi_valid": o == "true",
    "release_pin_valid": p == "true",
  },
  "release_pin": pin,
  "version": 1,
}
body = json.dumps(doc, separators=(",", ":"), sort_keys=True)
open(path, "w", encoding="utf-8").write(body)
PY2
}

write_report() {
  local count="$1"
  mkdir -p "$(dirname "${REPORT_FILE}")"
  python3 - "${FLEET_STAGE_ROOT}/build-train-probe.json" "${REPORT_FILE}" "${count}" "$(policy_digest)" <<'PY3'
import json, sys
snap_path, report_path, count, digest = sys.argv[1:5]
snap = json.load(open(snap_path, encoding="utf-8"))
probes = snap["probes"]
doc = {
  "approved_module_count": int(count),
  "build_attest_valid": probes["build_attest_valid"],
  "build_plan_valid": probes["build_plan_valid"],
  "debug_endpoint_blocked": probes["debug_endpoint_blocked"],
  "openapi_valid": probes["openapi_valid"],
  "plan_digest": snap["plan_digest"],
  "policy_applied": True,
  "policy_digest": digest,
  "release_pin_valid": probes["release_pin_valid"],
  "seal_root": snap["plan_seal"],
}
body = json.dumps(doc, separators=(",", ":"), sort_keys=True)
open(report_path, "w", encoding="utf-8").write(body)
PY3
}

append_journal() {
  python3 - "${FLEET_STAGE_ROOT}" <<'PY4'
import json, sys
from pathlib import Path
root = Path(sys.argv[1])
snap = json.loads((root / "build-train-probe.json").read_text(encoding="utf-8"))
journal = root / "run-journal.jsonl"
run_index = 1
if journal.is_file():
    run_index = sum(1 for line in journal.read_text(encoding="utf-8").splitlines() if line.strip()) + 1
line = json.dumps(
    {"run_index": run_index, "seal_root": snap["plan_seal"]},
    separators=(",", ":"),
    sort_keys=True,
)
with journal.open("a", encoding="utf-8") as fh:
    fh.write(line + "\n")
PY4
}

main() {
  log "waiting for api"
  wait_for_api

  local pin count openapi_ok pin_ok debug_ok build_ok attest_ok debug_code build_body attest_body
  local plan_digest plan_seal
  pin="$(read_release_pin)"
  count="$(approved_count)"

  if probe_openapi; then
    openapi_ok=true
  else
    openapi_ok=false
  fi

  if [[ -n "${pin}" ]]; then
    pin_ok=true
  else
    pin_ok=false
  fi

  write_policy "${pin}"
  log "policy rewritten"

  debug_code="$(probe_debug_endpoint)"
  if [[ "${debug_code}" == "404" ]]; then
    debug_ok=true
  else
    debug_ok=false
  fi

  build_body="$(probe_build_plan)"
  if [[ "${build_body}" == *"${EXPECTED_ORDER}"* ]]; then
    build_ok=true
  else
    build_ok=false
  fi

  attest_body="$(probe_build_attest)"
  plan_digest=""
  plan_seal=""
  attest_ok=false
  if [[ "${attest_body}" == *'"plan_seal"'* && "${attest_body}" == *'"plan_digest"'* ]]; then
    plan_digest="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["plan_digest"])' <<<"${attest_body}")"
    plan_seal="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["plan_seal"])' <<<"${attest_body}")"
    if [[ -n "${plan_digest}" && -n "${plan_seal}" && "${attest_body}" == *"${EXPECTED_ORDER}"* ]]; then
      attest_ok=true
    fi
  fi

  write_snapshot "${pin}" "${openapi_ok}" "${pin_ok}" "${debug_ok}" "${build_ok}" "${attest_ok}" "${plan_digest}" "${plan_seal}"

  if [[ "${openapi_ok}" != true || "${pin_ok}" != true || "${debug_ok}" != true || "${build_ok}" != true || "${attest_ok}" != true ]]; then
    log "validation failed: openapi=${openapi_ok} pin=${pin_ok} debug=${debug_ok} build=${build_ok} attest=${attest_ok}"
    exit 1
  fi

  write_report "${count}"
  append_journal
  log "report written to ${REPORT_FILE}"
}

main "$@"
