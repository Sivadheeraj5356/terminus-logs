#!/bin/bash
# Oracle — G-025: patch sources; offline cargo into writable target; install under /app/bin.
set -euo pipefail

APP_ROOT="${APP_ROOT:-/app}"
SOL_DIR="/solution"
if [ ! -d "${SOL_DIR}/files" ]; then
  SOL_DIR="/task/solution"
fi

export PATH="/usr/local/cargo/bin:/usr/bin:${PATH}"
export CARGO_HOME="${CARGO_HOME:-/usr/local/cargo}"
export RUSTUP_HOME="${RUSTUP_HOME:-/usr/local/rustup}"
export CARGO_INCREMENTAL=0
export CARGO_TARGET_DIR="${CARGO_TARGET_DIR:-/tmp/oracle-cargo-target}"
mkdir -p "${CARGO_TARGET_DIR}"

cd "${APP_ROOT}"

cp_rs() {
  local src="$1" dest="$2"
  sed 's/\r$//' "${src}" >"${dest}"
}

cp_rs "${SOL_DIR}/files/ingest.rs" "${APP_ROOT}/src/ingest/mod.rs"
cp_rs "${SOL_DIR}/files/haar.rs" "${APP_ROOT}/src/haar/mod.rs"
cp_rs "${SOL_DIR}/files/threshold.rs" "${APP_ROOT}/src/threshold/mod.rs"
cp_rs "${SOL_DIR}/files/seal.rs" "${APP_ROOT}/src/seal/mod.rs"
cp_rs "${SOL_DIR}/files/decompose_stage.rs" "${APP_ROOT}/src/decompose_stage/mod.rs"
cp_rs "${SOL_DIR}/files/export_stage.rs" "${APP_ROOT}/src/export_stage/mod.rs"

cargo build --release --locked --offline

ORACLE_BIN="${CARGO_TARGET_DIR}/release/haar-denoiser"
test -x "${ORACLE_BIN}"

mkdir -p "${APP_ROOT}/bin" "${APP_ROOT}/output" "${APP_ROOT}/state"
if cp -f "${ORACLE_BIN}" "${APP_ROOT}/bin/haar-denoiser" 2>/dev/null; then
  chmod 0755 "${APP_ROOT}/bin/haar-denoiser" || true
  RUN_BIN="${APP_ROOT}/bin/haar-denoiser"
else
  RUN_BIN="${ORACLE_BIN}"
fi
test -x "${RUN_BIN}"

rm -f "${APP_ROOT}/output/"*.json \
  "${APP_ROOT}/state/trace-snapshot.json" \
  "${APP_ROOT}/state/coeff-ledger.json" \
  "${APP_ROOT}/state/coeff-pack.json" \
  "${APP_ROOT}/state/threshold-journal.json"

"${RUN_BIN}" ingest-traces
"${RUN_BIN}" decompose-threshold
"${RUN_BIN}" reconstruct-export

test -f "${APP_ROOT}/state/trace-snapshot.json"
test -f "${APP_ROOT}/state/coeff-ledger.json"
test -f "${APP_ROOT}/state/coeff-pack.json"
test -f "${APP_ROOT}/state/threshold-journal.json"
test -f "${APP_ROOT}/output/denoised-traces.json"
test -f "${APP_ROOT}/output/noise-audit.json"

python3 - <<'PY'
import json
from pathlib import Path
pack = json.loads(Path("/app/state/coeff-pack.json").read_text())
assert pack["schema_version"] == 2
assert len(pack["pack_seal"]) == 64
assert len(pack["snapshot_digest"]) == 64
assert pack["entries"]
print("oracle coeff-pack seal ok")
PY
