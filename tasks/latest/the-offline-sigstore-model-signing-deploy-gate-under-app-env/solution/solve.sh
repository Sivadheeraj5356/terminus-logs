#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"

cp "$ROOT_DIR/patches/jp_w4.go" /app/environment/a6/b4/jp_w4.go
cp "$ROOT_DIR/patches/kt_n8.go" /app/environment/b2/c7/kt_n8.go
cp "$ROOT_DIR/patches/lu_v1.go" /app/environment/c9/d1/lu_v1.go

bash /app/environment/scripts/weld_bin.sh
bash /app/environment/tools/mx_run.sh gate --out /app/output/mx_pack.json
