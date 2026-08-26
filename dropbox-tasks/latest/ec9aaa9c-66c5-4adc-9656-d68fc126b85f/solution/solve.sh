#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

bash "$ROOT_DIR/apply_normalize.sh"
bash "$ROOT_DIR/apply_hop.sh"
bash "$ROOT_DIR/apply_bind.sh"
bash "$ROOT_DIR/apply_fence.sh"
bash "$ROOT_DIR/apply_engine.sh"
