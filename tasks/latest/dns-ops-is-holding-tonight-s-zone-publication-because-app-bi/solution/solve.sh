#!/bin/bash
set -euo pipefail
cd /app
PATCH_FILE=""
for candidate in \
  /workspace/solution/solution.patch \
  /solution/solution.patch \
  "$(dirname "$0")/solution.patch"
do
  if [ -f "$candidate" ]; then
    PATCH_FILE="$candidate"
    break
  fi
done
if [ -z "$PATCH_FILE" ]; then
  echo "solution.patch not found" >&2
  exit 1
fi
patch --dry-run -p1 < "$PATCH_FILE"
patch -p1 < "$PATCH_FILE"
bash /app/build.sh
