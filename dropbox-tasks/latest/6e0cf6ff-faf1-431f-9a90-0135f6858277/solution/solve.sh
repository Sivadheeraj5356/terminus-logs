#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd /app
/usr/bin/patch -p1 --forward --batch --quiet <"${ROOT_DIR}/sep_h.patch"
/usr/bin/patch -p1 --forward --batch --quiet <"${ROOT_DIR}/fold_g.patch"
/usr/bin/patch -p1 --forward --batch --quiet <"${ROOT_DIR}/tie_w.patch"
bash /app/driver/emit_ghost.sh
