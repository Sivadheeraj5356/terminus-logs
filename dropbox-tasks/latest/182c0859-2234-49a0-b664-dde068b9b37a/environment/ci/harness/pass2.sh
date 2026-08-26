#!/bin/bash
set -euo pipefail
# shellcheck source=/dev/null
source "$(dirname "$0")/common.sh"

touch_abi_profile
run_build incremental
emit_observation abi_touch --append
