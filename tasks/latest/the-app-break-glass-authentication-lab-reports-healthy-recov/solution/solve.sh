#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cd /app
patch -p1 --forward < "$ROOT_DIR/fix.patch"

make -C /app clean all
/app/scripts/regenerate-policy.sh
/app/scripts/verify-public.sh
