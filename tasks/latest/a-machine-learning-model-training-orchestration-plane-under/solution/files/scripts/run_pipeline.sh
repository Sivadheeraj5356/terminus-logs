#!/usr/bin/env bash
# AI Workflow Runtime — full A→H pipeline driver.
set -euo pipefail

export PATH="/usr/local/go/bin:/usr/local/bin:/tmp:${PATH:-}"

ROOT="${RUNTIME_ROOT:-${TB3_APP_ROOT:-/app}}"
BIN="${RUNTIME_BIN:-/tmp/runtime}"

export RUNTIME_ROOT="${ROOT}"
export RUNTIME_STATE_DIR="${RUNTIME_STATE_DIR:-${ROOT}/state}"
export RUNTIME_OUTPUT_DIR="${RUNTIME_OUTPUT_DIR:-${ROOT}/output}"
export RUNTIME_CACHE_DIR="${RUNTIME_CACHE_DIR:-${ROOT}/cache}"
export RUNTIME_CHECKPOINT_DIR="${RUNTIME_CHECKPOINT_DIR:-${ROOT}/state/checkpoints}"
export RUNTIME_WORKFLOW="${RUNTIME_WORKFLOW:-${ROOT}/testdata/workflows/ai_training.json}"
export RUNTIME_POLICY="${RUNTIME_POLICY:-${ROOT}/configs/policy.json}"
export RUNTIME_TOKEN_FILE="${RUNTIME_TOKEN_FILE:-${ROOT}/configs/hmac_signing_token.txt}"
export RUNTIME_EPOCH="${RUNTIME_EPOCH:-2024-06-15T12:00:00Z}"
export RUNTIME_SEED="${RUNTIME_SEED:-workflow-runtime-v1}"
export RUNTIME_MAX_RETRIES="${RUNTIME_MAX_RETRIES:-2}"
export RUNTIME_TIMEOUT_MS="${RUNTIME_TIMEOUT_MS:-100}"
export RUNTIME_WORKERS="${RUNTIME_WORKERS:-w0,w1,w2}"
export RUNTIME_STRICT_MODE="${RUNTIME_STRICT_MODE:-true}"
export RUNTIME_CHECKPOINT_EVERY="${RUNTIME_CHECKPOINT_EVERY:-2}"

cd "${ROOT}"

if [[ ! -x "${BIN}" ]]; then
  go build -o "${BIN}" ./cmd/runtime
fi

mkdir -p "${RUNTIME_STATE_DIR}" "${RUNTIME_OUTPUT_DIR}" "${RUNTIME_CACHE_DIR}" "${RUNTIME_CHECKPOINT_DIR}"

"${BIN}" run

echo "pipeline: completed A→H under ${ROOT}"
