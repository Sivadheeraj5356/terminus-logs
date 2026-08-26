#!/usr/bin/env bash
# Oracle solve — beta-six-lattice-chronicle token b6lc7e2a
# Installs ConchingAssay::WalkMath calibration kernels (new scientific subsystem), then fuses.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd /app

DEST="/app/lib/ConchingAssay/WalkMath"
mkdir -p "${DEST}"

cp "${ROOT_DIR}/files/TraceBatch.pm" "${DEST}/TraceBatch.pm"
cp "${ROOT_DIR}/files/PeakCapture.pm" "${DEST}/PeakCapture.pm"
cp "${ROOT_DIR}/files/LatticeResidual.pm" "${DEST}/LatticeResidual.pm"
cp "${ROOT_DIR}/files/PhaseSeal.pm" "${DEST}/PhaseSeal.pm"
cp "${ROOT_DIR}/files/ChronicleEmit.pm" "${DEST}/ChronicleEmit.pm"
cp "${ROOT_DIR}/files/Epoch.pm" "${DEST}/Epoch.pm"
cp "${ROOT_DIR}/files/BindManifest.pm" "${DEST}/BindManifest.pm"
cp "${ROOT_DIR}/files/HoldSpine.pm" "${DEST}/HoldSpine.pm"
cp "${ROOT_DIR}/files/HoldAdjacency.pm" "${DEST}/HoldAdjacency.pm"
cp "${ROOT_DIR}/files/CrossBatchConcordance.pm" "${DEST}/CrossBatchConcordance.pm"
cp "${ROOT_DIR}/files/ConcordanceCycle.pm" "${DEST}/ConcordanceCycle.pm"
cp "${ROOT_DIR}/files/EmitLane.pm" "${DEST}/EmitLane.pm"
cp "${ROOT_DIR}/files/AuditLog.pm" "${DEST}/AuditLog.pm"

for m in TraceBatch PeakCapture LatticeResidual PhaseSeal ChronicleEmit Epoch BindManifest HoldSpine HoldAdjacency CrossBatchConcordance ConcordanceCycle EmitLane AuditLog; do
  perl -c "${DEST}/${m}.pm"
done

TOOL=/app/bin/polymorph-chronicle
OUT=/app/output/lattice-chronicle-report.json
STATE_DIR=/app/state
mkdir -p /app/output "${STATE_DIR}" /app/var

test -x "${TOOL}"
test -d /app/kiln-run-traces
test -f /app/conching-network/conching-window-table.json
test -f /app/lattice-invariant-catalog/formulation-catalog.json

# Baseline inventory still works without closure kernels
"${TOOL}" inventory \
  --lattice-invariant-catalog /app/lattice-invariant-catalog/formulation-catalog.json \
  --output /tmp/b6lc-catalog-inventory.json
test -s /tmp/b6lc-catalog-inventory.json

"${TOOL}" fuse \
  --lattice-invariant-catalog /app/lattice-invariant-catalog/formulation-catalog.json \
  --conching-window /app/conching-network/conching-window-table.json \
  --kiln-traces /app/kiln-run-traces \
  --output "${OUT}"

test -s "${OUT}"
test -s "${STATE_DIR}/dsc-peak-capture.json"
test -s "${STATE_DIR}/torque-residual-snapshot.json"
test -s "${STATE_DIR}/hold-spine-ledger.json"
test -s "${STATE_DIR}/cross-batch-concordance.json"
test -s "${STATE_DIR}/concordance-cycle-basis.json"
test -s "${STATE_DIR}/polymorph-walk-seal.json"
test -s "${STATE_DIR}/chronicle-bind-manifest.json"
grep -q chronicle_digest "${OUT}"
