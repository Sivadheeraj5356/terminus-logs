#!/usr/bin/env bash
set -euo pipefail

TEST_DIR="${TEST_DIR:-/tests}"
APP_DIR="${APP_DIR:-/app}"

export PATH="/usr/local/cargo/bin:/usr/local/rustup/bin:/usr/local/bin:/usr/bin:/bin${PATH:+:${PATH}}"
export CARGO_HOME="${CARGO_HOME:-/usr/local/cargo}"
export RUSTUP_HOME="${RUSTUP_HOME:-/usr/local/rustup}"
export PYTHONPATH="${TEST_DIR}${PYTHONPATH:+:${PYTHONPATH}}"

# Platform static checks require the file to end with the echo reward block and
# no trailing `exit`. Propagate process status via EXIT trap using $rc.
VERIFIER_RC=1
_verifier_exit_trap() {
  trap - EXIT
  local code="${rc-}"
  if [ -z "${code}" ]; then
    code="${VERIFIER_RC:-1}"
  fi
  if [ "${code}" -eq 0 ]; then
    exit 0
  fi
  exit "${code}"
}
trap _verifier_exit_trap EXIT

write_reward() {
  local value="$1"
  mkdir -p /logs/verifier
  printf '%s\n' "$value" > /logs/verifier/reward.txt
}

fail_verifier() {
  local message="$1"
  local code="${2:-1}"

  printf '%s\n' "$message" >&2
  mkdir -p /logs/verifier
  printf '%s\n' "$message" > /logs/verifier/error.txt
  write_reward 0

  if [ "${code}" -eq 0 ]; then
    code=1
  fi
  VERIFIER_RC="${code}"
  trap - EXIT
  exit "${code}"
}

mkdir -p /logs/verifier /logs/agent
write_reward 0

[ -d "${APP_DIR}" ] || fail_verifier "error: missing ${APP_DIR}"
[ -d "${TEST_DIR}" ] || fail_verifier "error: missing ${TEST_DIR}"

mkdir -p "${APP_DIR}/output"

[ -f "${APP_DIR}/Cargo.toml" ] || fail_verifier "error: missing Cargo.toml"
[ -f "${APP_DIR}/Cargo.lock" ] || fail_verifier "error: missing Cargo.lock"
[ -f "${APP_DIR}/.cargo/config.toml" ] || fail_verifier "error: missing .cargo/config.toml"
[ -d "${APP_DIR}/vendor" ] || fail_verifier "error: missing vendor"

command -v cargo >/dev/null 2>&1 || fail_verifier "error: cargo not found in PATH"
command -v rustc >/dev/null 2>&1 || fail_verifier "error: rustc not found in PATH"
command -v python3 >/dev/null 2>&1 || fail_verifier "error: python3 not found in PATH"

python3 - <<'PY' || fail_verifier "error: pytest not available"
import importlib
importlib.import_module("pytest")
PY

python3 - <<'PY' || fail_verifier "error: pytest-json-ctrf not available"
import importlib
importlib.import_module("ctrf")
PY

python3 - <<'PY' || fail_verifier "error: Cargo config contains UTF-8 BOM"
from pathlib import Path
import sys

raw = Path("/app/.cargo/config.toml").read_bytes()
if raw.startswith(b"\xef\xbb\xbf"):
    raise SystemExit(1)
if not raw.startswith(b"["):
    raise SystemExit(1)
sys.exit(0)
PY

cd "${APP_DIR}"

rm -f "${APP_DIR}/output/report.json" "${APP_DIR}/output/report.json.tmp"

set +e
CARGO_NET_OFFLINE=true \
  cargo metadata \
    --locked \
    --offline \
    --format-version 1 \
    --no-deps \
    > /logs/verifier/cargo-metadata.log \
    2>&1
meta_rc=$?
set -e
if [ "${meta_rc}" -ne 0 ]; then
  printf '%s\n' "error: cargo metadata failed" >&2
  tail -n 80 /logs/verifier/cargo-metadata.log >&2 || true
  fail_verifier "error: cargo metadata failed" "${meta_rc}"
fi

rm -rf "${APP_DIR}/target"

set +e
CARGO_NET_OFFLINE=true \
  cargo build \
    --release \
    --locked \
    --offline \
    > /logs/verifier/cargo-build.log \
    2>&1
build_rc=$?
set -e
if [ "${build_rc}" -ne 0 ]; then
  printf '%s\n' "error: cargo build failed" >&2
  tail -n 80 /logs/verifier/cargo-build.log >&2 || true
  fail_verifier "error: cargo build failed" "${build_rc}"
fi

BIN="${APP_DIR}/target/release/tpm2-quote-attestor"
[ -x "${BIN}" ] || fail_verifier "error: missing release binary ${BIN}"

export TPM2_QUOTE_ATTESTOR_BIN="${BIN}"
export TPM2_QUOTE_APP_DIR="${APP_DIR}"
export TPM2_QUOTE_DATA_DIR="${APP_DIR}/data"
export TPM2_QUOTE_OUTPUT="${APP_DIR}/output/report.json"
export TPM2_QUOTE_FIXTURES="${TEST_DIR}/protected_fixtures"

[ -d "${TPM2_QUOTE_FIXTURES}" ] || fail_verifier "error: missing protected fixtures ${TPM2_QUOTE_FIXTURES}"

set +e
python3 -m pytest \
  -o cache_dir=/tmp/pytest_cache \
  --collect-only \
  -q \
  "${TEST_DIR}/test_outputs.py" \
  > /logs/verifier/collect-stdout.txt \
  2> /logs/verifier/collect-stderr.txt
collect_rc=$?
set -e

if [ "${collect_rc}" -ne 0 ]; then
  printf '%s\n' "error: pytest collection failed" >&2
  cat /logs/verifier/collect-stderr.txt >&2 || true
  fail_verifier "error: pytest collection failed" "${collect_rc}"
fi

EXPECTED_TESTS="$(cat <<'EOF'
test_01_cli_input_schema_and_duplicate_detection
test_02_bounded_quote_and_signature_binary_parsing
test_03_quote_magic_type_and_qualified_signer
test_04_attestation_key_and_ecdsa_signature_verification
test_05_nonce_binding_and_freshness
test_06_nonce_replay_and_consumption_boundary
test_07_pcr_selection_bitset_and_required_set
test_08_single_pcr_extend_replay
test_09_multi_pcr_replay_and_selected_digest
test_10_event_seq_order_and_physical_order_independence
test_11_event_log_device_binding_and_pcr_digest_mismatch
test_12_safe_clock_and_firmware_policy
test_13_required_reference_measurement
test_14_optional_and_unknown_measurements
test_15_forbidden_reference_measurement
test_16_reference_version_and_digest_mismatch
test_17_measurement_rule_duplicate_and_missing_behavior
test_18_event_order_constraints
test_19_reset_restart_and_clock_monotonicity
test_20_authenticated_rejection_state_commit_and_failure_precedence
test_21_dynamic_event_mutation_locality
test_22_five_seed_input_permutation_invariance
test_24_byte_identical_rerun_malformed_input_and_stale_cleanup
EOF
)"

COLLECTED_NAMES="$(
  grep -oE 'test_outputs\.py::test_[A-Za-z0-9_]+' /logs/verifier/collect-stdout.txt \
    | sed 's/^.*:://' \
    | sort
)"
COUNT="$(printf '%s\n' "${COLLECTED_NAMES}" | grep -c . || true)"
EXPECTED_SORTED="$(printf '%s\n' "${EXPECTED_TESTS}" | sort)"

if [ "${COUNT}" != "23" ] || [ "${COLLECTED_NAMES}" != "${EXPECTED_SORTED}" ]; then
  printf '%s\n' "error: expected exact 23 named tests; collected ${COUNT}" >&2
  printf '%s\n' "collected:" >&2
  printf '%s\n' "${COLLECTED_NAMES}" >&2
  fail_verifier "error: expected exactly 23 named tests, collected ${COUNT}"
fi

set +e
python3 -m pytest \
  -o cache_dir=/tmp/pytest_cache \
  --ctrf /logs/verifier/ctrf.json \
  "${TEST_DIR}/test_outputs.py" \
  -rA \
  > /logs/verifier/test-stdout.txt \
  2> /logs/verifier/test-stderr.txt
rc=$?

if [ "$rc" -eq 0 ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
