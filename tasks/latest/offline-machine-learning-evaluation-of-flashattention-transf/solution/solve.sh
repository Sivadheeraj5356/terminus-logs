#!/usr/bin/env bash
set -euo pipefail
if [ "${BASH_SOURCE[0]}" != "$0" ]; then
  exec bash "$0" "$@"
fi
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=== explore normative contracts ==="
head -n 12 /app/docs/behavior-register.md || true
head -n 8 /app/docs/tile-schedule-contract.md /app/docs/residency-seal-schema.md || true
ls -la /app/docs /app/bin /app/src/internal 2>/dev/null || true
ls -la "${SCRIPT_DIR}/oracle_crate/src" "${SCRIPT_DIR}/oracle_crate/src/bin" || true

echo "=== offline cargo build oracle crate ==="
export CARGO_HOME="${CARGO_HOME:-/usr/local/cargo}"
export CARGO_TARGET_DIR="/app/var/oracle-cargo-target"
rm -rf "${CARGO_TARGET_DIR}"
mkdir -p "${CARGO_TARGET_DIR}"
cd "${SCRIPT_DIR}/oracle_crate"
cargo build --release --locked --offline
install -m 0755 "${CARGO_TARGET_DIR}/release/kvtile-plan" /app/bin/kvtile-plan
install -m 0755 "${CARGO_TARGET_DIR}/release/kvtile-advance" /app/bin/kvtile-advance
install -m 0755 "${CARGO_TARGET_DIR}/release/kvtile-seal" /app/bin/kvtile-seal

bash /app/scripts/build.sh

rm -rf /app/data/* /app/output/*
mkdir -p /app/data /app/output
PACK="/app/fixtures/public/demo.kvpack"
PROFILE="/app/config/attn-profile.json"

/app/bin/kvtile-plan --pack "${PACK}" --profile "${PROFILE}"
/app/bin/kvtile-advance --profile "${PROFILE}"
/app/bin/kvtile-seal --seq-id demo --out /app/output/kvtile-residency-seal.json
test -s /app/output/kvtile-residency-seal.json
echo "=== oracle smoke ok ==="
