#!/usr/bin/env bash
set -euo pipefail

# Four-root oracle: repair ring seal, deadline latch, occupancy fold, and terminal packer.
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

log() { printf 'solve: %s\n' "$*"; }

require_tree() {
  local missing=0
  local p
  for p in \
    /app/environment/core/kz/ring.cpp \
    /app/environment/lane/ep/latch.cpp \
    /app/environment/lane/nx/quota.cpp \
    /app/environment/tools/sf_verify/pack.cpp \
    /app/environment/scripts/build_all.sh \
    /app/environment/migrations/v2_hold.sh
  do
    if [[ ! -e "$p" ]]; then
      log "missing required path: $p"
      missing=1
    fi
  done
  if [[ "$missing" -ne 0 ]]; then
    exit 2
  fi
}

restore_samples() {
  mkdir -p /app/output /app/output/stage /app/output/logs
  rm -f /app/output/epoch.ledger
  if [[ -x /app/environment/migrations/v2_hold.sh ]]; then
    /app/environment/migrations/v2_hold.sh --recover
  fi
  local sample
  for sample in circ_a.bin circ_b.bin clock_a.bin clock_b.bin burst_a.bin burst_b.bin; do
    if [[ ! -f "/app/environment/samples/raw_bytes/$sample" ]]; then
      log "sample still missing after recover: $sample"
      exit 3
    fi
  done
}

apply_all_fixes() {
  bash apply_fixes.sh
}

verify_touch_points() {
  if grep -q 'prior_admit_ok = 1' /app/environment/core/kz/ring.cpp; then
    log "ring.cpp still carries prior-admit dual window"
    exit 5
  fi
  if grep -q 'std::max(ctx->abs_deadline' /app/environment/lane/ep/latch.cpp; then
    log "latch.cpp still uses max composition"
    exit 5
  fi
  if grep -q 'now + ctx->abs_span' /app/environment/lane/ep/latch.cpp; then
    log "latch.cpp still extends hard deadline on soft refresh"
    exit 5
  fi
  if grep -q '(void)fence;' /app/environment/lane/nx/quota.cpp; then
    log "quota.cpp still ignores fence"
    exit 5
  fi
  if ! grep -q 'digest_sha256' /app/environment/tools/sf_verify/pack.cpp; then
    log "pack.cpp still omits digest fields"
    exit 5
  fi
  if ! grep -q 'dual_peak' /app/environment/tools/sf_verify/pack.cpp; then
    log "pack.cpp missing dual_peak field"
    exit 5
  fi
}

rebuild_model() {
  /app/environment/scripts/build_all.sh
  if [[ ! -x /app/bin/sf_verify ]]; then
    log "sf_verify binary missing after build"
    exit 6
  fi
  if [[ ! -x /app/environment/tools/sf_verify/sf_verify ]]; then
    log "in-tree sf_verify launcher/binary missing"
    exit 6
  fi
}

run_probes() {
  local build=/app/build
  local probes
  probes="$(cd "$(dirname "$0")/../tests/probes" 2>/dev/null && pwd || true)"
  if [[ -z "$probes" || ! -d "$probes" ]]; then
    probes=/tests/probes
  fi
  local out=/tmp/sf_oracle_probes
  mkdir -p "$out"
  g++ -std=c++17 -O0 "$probes/probe_seal.cpp" -o "$out/p_seal" \
    -I/app/environment/core/kz "$build/libkz_core.a" "$build/libsf_bootstrap.a"
  g++ -std=c++17 -O0 "$probes/probe_compose.cpp" -o "$out/p_compose" \
    -I/app/environment/lane/ep "$build/libep_lane.a" "$build/libsf_bootstrap.a"
  g++ -std=c++17 -O0 "$probes/probe_quota.cpp" -o "$out/p_quota" \
    -I/app/environment/lane/nx "$build/libnx_lane.a" "$build/libsf_bootstrap.a"
  "$out/p_seal"
  "$out/p_compose"
  "$out/p_quota"
}

run_matrix_twice() {
  local out="/app/output/witness.json"
  /app/bin/sf_verify --matrix all --profiles tight,loose --witness-out "$out"
  local rc1=$?
  /app/bin/sf_verify --matrix all --profiles tight,loose --witness-out "$out"
  local rc2=$?
  if [[ "$rc1" -ne 0 || "$rc2" -ne 0 ]]; then
    log "matrix rejected after oracle (rc1=$rc1 rc2=$rc2)"
    exit 7
  fi
  if [[ ! -s "$out" ]]; then
    log "witness.json empty"
    exit 8
  fi
  if ! grep -q 'digest_sha256' "$out"; then
    log "witness missing digest_sha256"
    exit 9
  fi
  if ! grep -q 'journal_tag' "$out"; then
    log "witness missing journal_tag"
    exit 9
  fi
  if ! grep -q 'dual_peak' "$out"; then
    log "witness missing dual_peak"
    exit 9
  fi
  if [[ ! -s /app/output/epoch.ledger ]]; then
    log "epoch.ledger missing"
    exit 9
  fi
}

skip_decoys() {
  local decoy
  for decoy in \
    /app/environment/core/kz/legacy_ring.cpp \
    /app/environment/lane/nx/stub_quota.cpp \
    /app/environment/tools/evt_pull/collector.cpp
  do
    if [[ ! -f "$decoy" ]]; then
      log "unexpected missing decoy: $decoy"
      exit 10
    fi
  done
}

main() {
  log "start four-root repair"
  cd "$SCRIPT_DIR"
  require_tree
  restore_samples
  skip_decoys
  apply_all_fixes
  verify_touch_points
  rebuild_model
  run_probes
  run_matrix_twice
  log "matrix witness accepted"
}

main "$@"
