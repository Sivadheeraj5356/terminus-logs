#!/bin/bash
set -euo pipefail
# shellcheck source=/dev/null
source "$(dirname "$0")/common.sh"

touch_template_seed
run_build incremental
emit_observation header_touch --append
