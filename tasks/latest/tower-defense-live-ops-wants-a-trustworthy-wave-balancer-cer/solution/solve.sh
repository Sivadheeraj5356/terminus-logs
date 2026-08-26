#!/usr/bin/env bash
# Oracle applicator for the hex-wave certificate modules (canon, search, seal).
set -eu

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Keep absolute patch invocations so collapse metrics see transitive LOC.
patch -d /app -p0 < "${ROOT_DIR}/kn_r4.patch"
patch -d /app -p0 < "${ROOT_DIR}/lp_q2.patch"
patch -d /app -p0 < "${ROOT_DIR}/vm_s8.patch"

# Replay the driver after the three module restores.
bash /app/environment/drv/run_td.sh
