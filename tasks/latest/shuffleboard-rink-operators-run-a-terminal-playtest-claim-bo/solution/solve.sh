# Oracle solve — task identity shuffleboard-wax-lane-claim-board token 762de05d
#!/usr/bin/env bash
# Oracle solve — shuffleboard-wax-lane-claim-board (offline G-025) token wlx9c2a7
set -euo pipefail

export PATH="/app/bin:/usr/local/bin:/usr/local/go/bin:/opt/verifier-scripts:${PATH}"
export CGO_ENABLED=0

APP_ROOT="/app"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ ! -d "${ROOT_DIR}/patches" ]; then
  if [ -d "/solution/patches" ]; then ROOT_DIR="/solution";
  elif [ -d "/task/solution/patches" ]; then ROOT_DIR="/task/solution"; fi
fi

/usr/bin/patch -p1 -d "${APP_ROOT}" < "${ROOT_DIR}/patches/pkg_matchplan_solver.go.patch"
/usr/bin/patch -p1 -d "${APP_ROOT}" < "${ROOT_DIR}/patches/pkg_surfaceband_rules.go.patch"
/usr/bin/patch -p1 -d "${APP_ROOT}" < "${ROOT_DIR}/patches/pkg_matchticket_slate.go.patch"
/usr/bin/patch -p1 -d "${APP_ROOT}" < "${ROOT_DIR}/patches/pkg_scoreledger_ledger.go.patch"
/usr/bin/patch -p1 -d "${APP_ROOT}" < "${ROOT_DIR}/patches/pkg_boardcmd_run.go.patch"
/usr/bin/patch -p1 -d "${APP_ROOT}" < "${ROOT_DIR}/patches/pkg_diskset_lots.go.patch"

if ! /opt/verifier-scripts/rebuild-waxlane-allot; then
  cd "${APP_ROOT}"
  go build -mod=readonly -o /app/bin/waxlane-allot ./cmd/waxlane-allot
  chmod +x /app/bin/waxlane-allot
fi
test -x "${APP_ROOT}/bin/waxlane-allot"
mkdir -p /app/output /app/state
rm -f /app/state/chalk-epoch /app/state/chalk-slate.json
"${APP_ROOT}/bin/waxlane-allot" claim \
  --court /app/data/rink-lanes.json \
  --lots /app/data/disk-packages.json \
  --slate /app/state/chalk-slate.json \
  --epoch /app/state/chalk-epoch \
  --ledger /app/output/wax-lane-claim-ledger.json
test -s /app/state/chalk-slate.json
test -s /app/output/wax-lane-claim-ledger.json
