#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"

fixes_applied() {
  grep -Fq 'carry_token' /app/environment/deps/w7_token.sh \
    && ! grep -Fq 'carry_cache.json' /app/environment/deps/w7_token.sh \
    && ! grep -Fq 'probe_order.json' /app/environment/deps/w3_bind.sh \
    && grep -Fq 'wave_b.get("carry_token"' /app/environment/deps/w8_stage.sh \
    && grep -Fq 'wave_c.get("carry_token"' /app/environment/deps/w8_stage.sh \
    && grep -Fq 'chroot_order = order' /app/environment/deps/w3_bind.sh \
    && grep -Fq 'obj_names = sorted(o["name"]' /app/environment/deps/w3_bind.sh \
    && grep -Fq 'stamp_digest' /app/environment/deps/w3_bind.sh \
    && grep -Fq 'sorted(sys.argv[3:])' /app/environment/lib/stamp_k.sh \
    && grep -Fq '";".join(names)' /app/environment/lib/stamp_k.sh \
    && grep -Fq '(-weights[n], n)' /app/environment/lib/stamp_k.sh \
    && grep -Fq 'lane_seq = ["B", "O"]' /app/environment/lane/phase_w1.sh \
    && grep -Fq 'active_wave.json' /app/environment/lane/phase_w1.sh \
    && grep -Fq 'weight_order' /app/environment/lane/phase_w1.sh \
    && ! grep -Fq 'seg_hook_gen' /app/environment/lane/phase_w1.sh \
    && grep -Fq 'if blob_epoch == hook_gen:' /app/environment/frame/sched_w2.sh \
    && grep -Fq 'commits.get("B", False)' /app/environment/emit/metric_k.sh \
    && ! grep -Fq 'inherit_lane' /app/environment/emit/metric_k.sh \
    && grep -Fq 'journal_union' /app/environment/emit/metric_k.sh \
    && ! grep -Fq 'rows.sort(key=lambda r' /app/environment/emit/metric_k.sh \
    && grep -Fq 'source /app/environment/emit/metric_k.sh' /app/environment/emit/trace_w4.sh \
    && grep -Fq 'status_token": status' /app/environment/emit/trace_w4.sh \
    && grep -Fq 'mode = "weight"' /app/environment/work/run_w5.sh \
    && ! grep -Fq 'weight" if profile' /app/environment/work/run_w5.sh \
    && grep -Fq '"profile": profile' /app/environment/work/run_w5.sh \
    && grep -Fq 'fn_r3 "$JOURNAL" 1' /app/environment/driver/exec_w0.sh \
    && grep -Fq 'rm -f /app/.staging/carry_cache.json' /app/environment/driver/exec_w0.sh \
    && ! grep -Fq 'last_profile.txt' /app/environment/driver/exec_w0.sh \
    && grep -Fq 'fn_wave_stage "$WAVE_REL"' /app/environment/driver/exec_w0.sh \
    && grep -Fq 'if stamp == ledger.get("last_stamp")' /app/environment/lib/rev_k.sh
}

if [[ ! -f patches/all-fixes.patch ]]; then
  echo "ERROR: missing patch patches/all-fixes.patch" >&2
  exit 1
fi

if ! fixes_applied; then
  patch -p1 --fuzz=0 --no-backup-if-mismatch -d /app < patches/all-fixes.patch
fi

if ! fixes_applied; then
  echo "ERROR: environment fixes are not present after patching" >&2
  exit 1
fi

rm -rf /app/.staging /app/output
mkdir -p /app/output

bash /app/environment/driver/exec_w0.sh --profile warm
bash /app/environment/driver/exec_w0.sh --profile cold
bash /app/environment/driver/exec_w0.sh --profile cold --merge
bash /app/environment/driver/exec_w0.sh --profile cold --merge-tier 2

echo "Solution applied - outputs regenerated for warm, cold, merge, and tier-2 profiles"
