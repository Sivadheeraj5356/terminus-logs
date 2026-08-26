#!/usr/bin/env bash
set -euo pipefail
APP_ROOT="${APP_ROOT:-/app}"
STATE="${APP_ROOT}/state"
OUTPUT="${APP_ROOT}/output"
TIDE_SNAPSHOT="${STATE}/tide-snapshot.json"
ROV_INDEX="${STATE}/rov-index.json"
BERTH_STAGING="${STATE}/berth-staging.json"
TRANSFER_CERT="${STATE}/transfer-cert.json"
EXPORT_BIND="${STATE}/export-bind.json"
INGEST_MANIFEST="${STATE}/ingest-manifest.json"
RESUPPLY_PLAN="${OUTPUT}/resupply-plan.json"
UTIL_REPORT="${OUTPUT}/utilization-report.json"
RUN_SEQ="${STATE}/run-sequence.json"
RUN_SEQUENCE_FILE="${RUN_SEQ}"
EXPORT_SEAL="${STATE}/export-seal.json"
O2_FREEZE="${STATE}/o2-priority-freeze.json"
ensure_dirs() { mkdir -p "${STATE}" "${OUTPUT}"; }
