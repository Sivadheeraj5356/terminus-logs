#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ORACLE_SRC="${SCRIPT_DIR}/oracle_src"

export PATH="/usr/local/cargo/bin:/root/.cargo/bin:/usr/local/bin:/usr/bin:/bin:${PATH:-}"

command -v cargo >/dev/null 2>&1 || {
  echo "error: cargo not found" >&2
  exit 1
}

test -d "${ORACLE_SRC}/src" || {
  echo "error: Oracle source missing at ${ORACLE_SRC}/src" >&2
  exit 1
}
test -f "${ORACLE_SRC}/Cargo.toml" || {
  echo "error: Oracle Cargo.toml missing" >&2
  exit 1
}
test -f "${ORACLE_SRC}/Cargo.lock" || {
  echo "error: Oracle Cargo.lock missing" >&2
  exit 1
}

cd /app

rm -rf /app/src
mkdir -p /app/src
cp -a "${ORACLE_SRC}/src/." /app/src/

cp "${ORACLE_SRC}/Cargo.toml" /app/Cargo.toml
cp "${ORACLE_SRC}/Cargo.lock" /app/Cargo.lock

test -d /app/vendor || {
  echo "error: /app/vendor missing" >&2
  exit 1
}

test -f /app/.cargo/config.toml || {
  echo "error: /app/.cargo/config.toml missing" >&2
  exit 1
}

rm -rf /app/target
mkdir -p /app/output
rm -f /app/output/report.json /app/output/report.json.tmp
rm -f /app/output/oracle-smoke-report.json /app/output/oracle-smoke-report.json.tmp

cargo build --release --locked --offline

SOLVER_BIN="/app/target/release/lunar-regolith-solver"

test -x "$SOLVER_BIN" || {
  echo "error: Oracle binary missing at $SOLVER_BIN" >&2
  exit 1
}

SMOKE_REPORT="/app/output/oracle-smoke-report.json"
rm -f "$SMOKE_REPORT" "${SMOKE_REPORT}.tmp"

"$SOLVER_BIN" \
  --data-dir /app/data \
  --output "$SMOKE_REPORT"

python3 - "$SMOKE_REPORT" <<'PY'
import json
import math
import sys
from pathlib import Path

required = [
    "time_step_rows",
    "temperature_rows",
    "surface_flux_rows",
    "radiometer_rows",
    "inverse_fit_rows",
    "solver_diagnostics",
    "summary",
]
nonempty = [
    "time_step_rows",
    "temperature_rows",
    "surface_flux_rows",
    "radiometer_rows",
    "inverse_fit_rows",
    "solver_diagnostics",
]

path = Path(sys.argv[1])
if not path.is_file() or path.stat().st_size == 0:
    sys.exit("oracle smoke: report missing or empty")
data = json.loads(path.read_text(encoding="utf-8"))
if not isinstance(data, dict):
    sys.exit("oracle smoke: report is not a JSON object")
if set(data.keys()) != set(required):
    sys.exit(f"oracle smoke: unexpected top-level keys: {sorted(data.keys())}")

for key in nonempty:
    rows = data.get(key)
    if not isinstance(rows, list) or not rows:
        sys.exit(f"oracle smoke: {key} must be a nonempty list")

summary = data.get("summary") or {}
if int(summary.get("case_count") or 0) < 1:
    sys.exit("oracle smoke: summary.case_count must be > 0")
if int(summary.get("observation_count") or 0) < 1:
    sys.exit("oracle smoke: summary.observation_count must be > 0")


def check_finite(obj, path=""):
    if isinstance(obj, bool) or obj is None:
        return
    if isinstance(obj, (int, float)):
        if not math.isfinite(float(obj)):
            sys.exit(f"oracle smoke: non-finite number at {path}")
        return
    if isinstance(obj, list):
        for i, v in enumerate(obj):
            check_finite(v, f"{path}[{i}]")
        return
    if isinstance(obj, dict):
        for k, v in obj.items():
            check_finite(v, f"{path}.{k}" if path else k)


check_finite(data)
print("oracle smoke validation ok")
PY

echo "Oracle smoke succeeded; report at $SMOKE_REPORT"
