#!/bin/bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cp "${ROOT_DIR}/fixed/cfg_lane.rb" /app/environment/r41/cfg_lane.rb
cp "${ROOT_DIR}/fixed/lane_cache.rb" /app/environment/r41/lane_cache.rb
cp "${ROOT_DIR}/fixed/emit_w.rb" /app/environment/r42/emit_w.rb
cp "${ROOT_DIR}/fixed/gate_p.rb" /app/environment/r43/gate_p.rb
cp "${ROOT_DIR}/fixed/rot_fold.rb" /app/environment/r43/rot_fold.rb
rm -rf /app/environment/r43/.scratch
mkdir -p /app/environment/r43/.scratch
