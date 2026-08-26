#!/usr/bin/env bash
set -euo pipefail

ENV_ROOT="/app/environment"
source "${ENV_ROOT}/lib/stamp_k.sh"
source "${ENV_ROOT}/lib/rev_k.sh"
source "${ENV_ROOT}/deps/w3_bind.sh"
source "${ENV_ROOT}/deps/w8_stage.sh"
source "${ENV_ROOT}/lane/phase_w1.sh"
source "${ENV_ROOT}/frame/sched_w2.sh"
source "${ENV_ROOT}/emit/trace_w4.sh"

usage() {
  echo "usage: exec_w0.sh --profile warm|cold [--merge | --merge-tier N]" >&2
  exit 2
}

PROFILE=""
MERGE_TIER=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --profile) PROFILE="$2"; shift 2 ;;
    --merge) MERGE_TIER=1; shift ;;
    --merge-tier) MERGE_TIER="$2"; shift 2 ;;
    -h|--help) usage ;;
    *) usage ;;
  esac
done
[[ -n "$PROFILE" ]] || usage

SESSION_CTX="/app/.staging/session_ctx.json"
CTX_KEY="${PROFILE}:${MERGE_TIER}"

mkdir -p /app/output /app/.staging
echo "$CTX_KEY" > "$SESSION_CTX"
if [[ ! -f /app/.staging/epoch_ledger.json ]]; then
  cp -f "${ENV_ROOT}/state/epoch_ledger.json" /app/.staging/epoch_ledger.json 2>/dev/null || true
fi
bash "${ENV_ROOT}/work/run_w5.sh" --profile "$PROFILE"

WAVE_REL="bundles/waves/wave_a.json"
if [[ "$MERGE_TIER" -eq 1 ]]; then
  WAVE_REL="bundles/waves/wave_b.json"
elif [[ "$MERGE_TIER" -eq 2 ]]; then
  WAVE_REL="bundles/waves/wave_c.json"
fi

LAST_PROFILE="/app/.staging/last_profile.txt"
if [[ ! -f "$LAST_PROFILE" ]] || [[ "$(cat "$LAST_PROFILE")" != "$PROFILE" ]] || [[ ! -f /app/.staging/active_wave.json ]]; then
  fn_wave_stage "$WAVE_REL" "$MERGE_TIER"
  echo "$PROFILE" > "$LAST_PROFILE"
fi

HOST_IDX="/app/.staging/host_index.json"
CHROOT_IDX="/app/.staging/chroot_index.json"
MANIFEST_OUT="/app/output/staging_manifest.json"
fn_r1 "$HOST_IDX" "$CHROOT_IDX" "$PROFILE" "$MANIFEST_OUT"
rev_touch "$MANIFEST_OUT"

JOURNAL="/app/.staging/phase_journal.json"
fn_r2 "$WAVE_REL" "$JOURNAL"

fn_r3 "$JOURNAL" 0

cp "$JOURNAL" /app/output/phase_journal.json
fn_r4 "$MANIFEST_OUT" /app/output/phase_journal.json /app/output/loader_trace.json

printf 'status=CLEAN profile=%s\n' "$PROFILE" >&2
