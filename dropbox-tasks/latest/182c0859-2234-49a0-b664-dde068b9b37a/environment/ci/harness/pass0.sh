#!/bin/bash
set -euo pipefail
# shellcheck source=/dev/null
source "$(dirname "$0")/common.sh"

clean_workspace
run_build full
emit_observation cold
