#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FILES="${SCRIPT_DIR}/files"

cp "${FILES}/"*.cpp /app/src/

bash /app/tools/build.sh
