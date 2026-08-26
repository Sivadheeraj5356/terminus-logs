#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/app}"
SOLUTION_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ORACLE_DIR="${SOLUTION_DIR}/oracle_src"

export PATH="/usr/local/cargo/bin:/usr/local/rustup/bin:/usr/local/bin:/usr/bin:/bin${PATH:+:${PATH}}"
export CARGO_HOME="${CARGO_HOME:-/usr/local/cargo}"
export RUSTUP_HOME="${RUSTUP_HOME:-/usr/local/rustup}"

fail() {
  printf '%s\n' "$1" >&2
  exit 1
}

mkdir -p /logs/agent /logs/verifier

[ -d "${APP_DIR}" ] || fail "error: missing ${APP_DIR}"
[ -d "${APP_DIR}/vendor" ] || fail "error: missing ${APP_DIR}/vendor"
[ -f "${APP_DIR}/.cargo/config.toml" ] || fail "error: missing ${APP_DIR}/.cargo/config.toml"
[ -f "${APP_DIR}/Cargo.toml" ] || fail "error: missing ${APP_DIR}/Cargo.toml"
[ -f "${APP_DIR}/Cargo.lock" ] || fail "error: missing ${APP_DIR}/Cargo.lock"
[ -d "${ORACLE_DIR}/src" ] || fail "error: missing Oracle src"
[ -f "${ORACLE_DIR}/Cargo.toml" ] || fail "error: missing Oracle Cargo.toml"
[ -f "${ORACLE_DIR}/Cargo.lock" ] || fail "error: missing Oracle Cargo.lock"
command -v cargo >/dev/null 2>&1 || fail "error: cargo not found"
command -v rustc >/dev/null 2>&1 || fail "error: rustc not found"

mkdir -p "${APP_DIR}/output"

python3 - <<'PY' || fail "error: Cargo config contains UTF-8 BOM or is unreadable"
from pathlib import Path
import sys

p = Path("/app/.cargo/config.toml")
raw = p.read_bytes()
if raw.startswith(b"\xef\xbb\xbf"):
    raise SystemExit(1)
if not raw.startswith(b"["):
    raise SystemExit(1)
sys.exit(0)
PY

cmp -s "${APP_DIR}/Cargo.toml" "${ORACLE_DIR}/Cargo.toml" \
  || fail "error: application and Oracle Cargo.toml differ"
cmp -s "${APP_DIR}/Cargo.lock" "${ORACLE_DIR}/Cargo.lock" \
  || fail "error: application and Oracle Cargo.lock differ"

rm -rf "${APP_DIR}/target"
rm -f "${APP_DIR}/output/report.json" "${APP_DIR}/output/report.json.tmp"

rm -rf "${APP_DIR}/src"
mkdir -p "${APP_DIR}/src"
cp -a "${ORACLE_DIR}/src/." "${APP_DIR}/src/"
cp -a "${ORACLE_DIR}/Cargo.toml" "${APP_DIR}/Cargo.toml"
cp -a "${ORACLE_DIR}/Cargo.lock" "${APP_DIR}/Cargo.lock"

cd "${APP_DIR}"

CARGO_NET_OFFLINE=true \
  cargo metadata --locked --offline --format-version 1 --no-deps \
  > /logs/agent/oracle-cargo-metadata.log 2>&1 \
  || fail "error: Oracle cargo metadata failed (see /logs/agent/oracle-cargo-metadata.log)"

CARGO_NET_OFFLINE=true \
  cargo build --release --locked --offline \
  > /logs/agent/oracle-cargo-build.log 2>&1 \
  || {
    printf '%s\n' "error: Oracle cargo build failed" >&2
    tail -n 80 /logs/agent/oracle-cargo-build.log >&2 || true
    exit 1
  }

BIN="${APP_DIR}/target/release/tpm2-quote-attestor"
[ -x "${BIN}" ] || fail "error: missing release binary ${BIN}"

"${BIN}" \
  --data-dir "${APP_DIR}/data" \
  --output "${APP_DIR}/output/report.json"

python3 - <<'PY' || fail "error: Oracle smoke report validation failed"
import json
from pathlib import Path

REQUIRED = {
    "request_rows",
    "quote_rows",
    "event_rows",
    "pcr_rows",
    "reference_match_rows",
    "counter_rows",
    "nonce_rows",
    "conflict_rows",
    "summary",
}

path = Path("/app/output/report.json")
if not path.is_file():
    raise SystemExit("missing report")
report = json.loads(path.read_text(encoding="utf-8"))
if set(report.keys()) != REQUIRED:
    raise SystemExit(f"unexpected keys: {sorted(report.keys())}")
summary = report["summary"]
if summary.get("request_count") != 16:
    raise SystemExit(f"request_count={summary.get('request_count')}")
if summary.get("accepted_request_count") != 4:
    raise SystemExit(f"accepted_request_count={summary.get('accepted_request_count')}")
if summary.get("rejected_request_count") != 12:
    raise SystemExit(f"rejected_request_count={summary.get('rejected_request_count')}")
PY

rm -f "${APP_DIR}/output/report.json" "${APP_DIR}/output/report.json.tmp"

printf '%s\n' "ORACLE_OK"
exit 0
