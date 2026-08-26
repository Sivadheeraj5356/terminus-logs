#!/bin/bash
set -euo pipefail

# Terminal-Bench Canary
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd /app
patch -p0 < "$ROOT_DIR/patches/expand_k.patch"
patch -p0 < "$ROOT_DIR/patches/fold_m.patch"
patch -p0 < "$ROOT_DIR/patches/seal_p.patch"
bash /app/environment/tools/rebuild_bin.sh
mkdir -p /app/output
/app/bin/lane_matrix --fixtures /app/fixtures --spec /app/spec --out /app/output/coverage_map.json
