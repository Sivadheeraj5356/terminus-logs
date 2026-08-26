#!/bin/bash
set -euo pipefail
PROFILE="${1:-amber}"
/app/bin/mux audit --profile "$PROFILE"
