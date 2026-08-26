#!/usr/bin/env bash
set -euo pipefail
export PATH="/usr/local/go/bin:${PATH}"
bash /app/scripts/ensure-limits.sh
cd /app
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
patch -p1 --forward < "${ROOT_DIR}/fix.patch"
gofmt -w internal/keys internal/rollover internal/serial internal/nsec3 internal/journal internal/manifest internal/signing internal/publication
make -C /app build
/app/scripts/reset-workflows.sh
/app/scripts/repro.sh normal
/app/scripts/repro.sh interrupted
/app/scripts/repro.sh rollback
/app/scripts/repro.sh wrap
