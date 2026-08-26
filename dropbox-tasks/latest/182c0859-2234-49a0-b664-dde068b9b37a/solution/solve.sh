#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cd /app/environment

patch -p0 < "${ROOT_DIR}/patches/graph_digest.patch"
patch -p0 < "${ROOT_DIR}/patches/sidecar_store.patch"
patch -p0 < "${ROOT_DIR}/patches/drift_scan.patch"
patch -p0 < "${ROOT_DIR}/patches/relink_order.patch"
patch -p0 < "${ROOT_DIR}/patches/replay_ledger.patch"
patch -p0 < "${ROOT_DIR}/patches/tu_orchestrator.patch"
patch -p0 < "${ROOT_DIR}/patches/epoch_courier.patch"

bash /app/environment/ci/harness/pass0.sh
bash /app/environment/ci/harness/pass1.sh
