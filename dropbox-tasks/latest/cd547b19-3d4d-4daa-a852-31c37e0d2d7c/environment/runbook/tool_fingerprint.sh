#!/usr/bin/env bash
set -euo pipefail

ENV_ROOT=${1:-/app/environment}
find "$ENV_ROOT/tools/genabi" -type f \( -name '*.cpp' -o -name '*.hpp' \) \
  | sort \
  | xargs sha256sum \
  | sha256sum \
  | awk '{print $1}'
