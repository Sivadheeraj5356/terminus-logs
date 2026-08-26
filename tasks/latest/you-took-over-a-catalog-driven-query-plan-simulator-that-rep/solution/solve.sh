#!/usr/bin/env bash
# Oracle: reconcile pause_resume plan rows with the tape replay contract.
set -euo pipefail

log() { printf '%s\n' "$*" >&2; }

root_dir="${TASK_APP_ROOT:-/app}"
cd "${root_dir}"

log "=== step 1: read audit contracts and tape semantics ==="
sed -n '1,32p' "${root_dir}/doc/plan_audit_contract.txt"
cat "${root_dir}/stubs/replay_contract.txt"
sed -n '1,10p' "${root_dir}/doc/semantics.txt"
sed -n '1,6p' "${root_dir}/cfg/runtime.toml"

log "=== step 2: baseline hook and mismatch snapshot ==="
"${root_dir}/ci/build_and_load.sh"
python3 - <<'PY'
import json
from pathlib import Path

root = Path("/app")
doc = json.loads((root / "output/plan_audit.json").read_text(encoding="utf-8"))
print("summary", doc["summary"])
bad = [
    (row["scenario_id"], row["mode"], row.get("pair_ok"), row.get("step_gamma_id"))
    for row in doc["scenarios"]
    if row["mode"] == "pause_resume" and not row.get("pair_ok")
]
print("pause_resume mismatches", len(bad))
for item in bad[:5]:
    print(" sample", item)
PY

log "=== step 3: trace resume path in the frozen driver ==="
grep -n 'merge_a\|lookup_c\|probe_d\|resume_pending\|est_b' \
  "${root_dir}/engine/plan_drive.c" || true
grep -n 'merge_bias\|weave_u_fold\|cord_bias\|carry_bias' \
  "${root_dir}/rack_o/"*.c "${root_dir}/weave_u/"*.c 2>/dev/null | head -n 20 || true

log "=== step 4: repair catalog generation merge (rack_o / weave_u) ==="
cat > "${root_dir}/rack_o/merge_bias.c" <<'EOF'
#include "plan_types.h"

uint32_t weave_u_fold(uint32_t persisted, uint32_t live);

uint32_t merge_bias_wrap(uint32_t persisted, uint32_t live) {
  (void)persisted;
  return weave_u_fold(persisted, live);
}
EOF

cat > "${root_dir}/weave_u/cord_bias.c" <<'EOF'
#include "plan_types.h"

uint32_t cord_bias_pick(uint32_t persisted, uint32_t live) {
  (void)persisted;
  return live;
}
EOF

cat > "${root_dir}/weave_u/tie_fold.c" <<'EOF'
#include "plan_types.h"

uint32_t carry_bias(uint32_t persisted, uint32_t live);

uint32_t weave_u_fold(uint32_t persisted, uint32_t live) {
  return carry_bias(persisted, live);
}
EOF

cat > "${root_dir}/weave_u/slot_weft.c" <<'EOF'
#include "plan_types.h"

uint32_t coil_mesh_pick(uint32_t persisted, uint32_t live);

uint32_t slot_weft_pick(uint32_t persisted, uint32_t live) {
  return coil_mesh_pick(persisted, live);
}
EOF

log "=== step 5: repair bound estimates and bucket indexing (loom_p / shard_k) ==="
cat > "${root_dir}/loom_p/range_est.c" <<'EOF'
#include "plan_types.h"

double shard_k_lane(const pl_table *live, const pl_table *snap, int use_snap, int pred_bucket);

double est_b(const pl_table *live, const pl_table *snap, int use_snap_bounds, int pred_bucket) {
  return shard_k_lane(live, snap, use_snap_bounds, pred_bucket);
}
EOF

cat > "${root_dir}/shard_k/cord_lane.c" <<'EOF'
#include "plan_types.h"

int cord_lane_bucket(int pred_bucket, int use_snap) {
  (void)use_snap;
  return pred_bucket;
}
EOF

cat > "${root_dir}/shard_k/bound_lane.c" <<'EOF'
#include "plan_types.h"

int mix_idx(int pred_bucket, int use_snap);

double shard_k_lane(const pl_table *live, const pl_table *snap, int use_snap, int pred_bucket) {
  if (!live) {
    return 1.0;
  }
  int bucket = mix_idx(pred_bucket, use_snap);
  if (bucket < 0 || bucket >= PL_MAX_BUCK) {
    return 1.0;
  }
  const pl_table *bound_src = live;
  if (use_snap && snap) {
    bound_src = snap;
  }
  uint32_t bucket_count = live->buckets;
  if (bucket_count == 0) {
    return 1.0;
  }
  uint32_t hi = bound_src->bounds[bucket];
  if (hi == 0) {
    return 1.0;
  }
  return (double)bucket_count / (double)(hi + 1);
}
EOF

cat > "${root_dir}/shard_k/mix_idx.c" <<'EOF'
#include "plan_types.h"

int lane_weft_bucket(int pred_bucket, int use_snap);

int mix_idx(int pred_bucket, int use_snap) {
  return lane_weft_bucket(pred_bucket, use_snap);
}
EOF

log "=== step 6: repair memo slot validity (spool_q) ==="
cat > "${root_dir}/spool_q/cord_ring.c" <<'EOF'
#include "plan_types.h"

int cord_ring_ok(uint32_t memo_gen, uint32_t gen) {
  return memo_gen == gen ? 1 : 0;
}
EOF

cat > "${root_dir}/spool_q/ring_weft.c" <<'EOF'
#include "plan_types.h"

int loop_mesh_ok(uint32_t memo_gen, uint32_t gen);

int ring_weft_ok(uint32_t memo_gen, uint32_t gen) {
  return loop_mesh_ok(memo_gen, gen);
}
EOF

cat > "${root_dir}/spool_q/epoch_slot.c" <<'EOF'
#include "plan_types.h"

int gen_ring_ok(uint32_t memo_gen, uint32_t gen);

int epoch_slot_valid(const pl_ctx *ctx, uint64_t fp, uint32_t gen) {
  if (!ctx || !ctx->memo_valid || ctx->memo_fp != fp) {
    return 0;
  }
  return gen_ring_ok(ctx->memo_gen, gen);
}
EOF

cat > "${root_dir}/spool_q/cache_get.c" <<'EOF'
#include "plan_types.h"

#include <string.h>

int epoch_slot_valid(const pl_ctx *ctx, uint64_t fp, uint32_t gen);

int lookup_c(char *alpha, char *beta, char *gamma, uint64_t fp, uint32_t gen, const pl_ctx *ctx) {
  if (!epoch_slot_valid(ctx, fp, gen)) {
    return 0;
  }
  strncpy(alpha, ctx->memo_alpha, 31);
  strncpy(beta, ctx->memo_beta, 31);
  strncpy(gamma, ctx->memo_gamma, 31);
  alpha[31] = '\0';
  beta[31] = '\0';
  gamma[31] = '\0';
  return 1;
}

void store_c(pl_ctx *ctx, uint64_t fp, uint32_t gen, const char *alpha, const char *beta,
             const char *gamma) {
  if (!ctx || !alpha || !beta || !gamma) {
    return;
  }
  ctx->memo_fp = fp;
  ctx->memo_gen = gen;
  strncpy(ctx->memo_alpha, alpha, 31);
  strncpy(ctx->memo_beta, beta, 31);
  strncpy(ctx->memo_gamma, gamma, 31);
  ctx->memo_alpha[31] = '\0';
  ctx->memo_beta[31] = '\0';
  ctx->memo_gamma[31] = '\0';
  ctx->memo_valid = 1;
}
EOF

log "=== step 7: repair visibility probe chain (vault_r) ==="
cat > "${root_dir}/vault_r/page_gate.c" <<'EOF'
#include "plan_types.h"

int stamp_line_ok(uint32_t vis_gen, uint32_t live_vis, uint64_t row_est, int partial_req);

int probe_d(uint32_t vis_gen, uint32_t live_vis, uint64_t row_est, int partial_req) {
  return stamp_line_ok(vis_gen, live_vis, row_est, partial_req);
}
EOF

cat > "${root_dir}/vault_r/fold_weft.c" <<'EOF'
#include "plan_types.h"

int phase_mesh_ok(uint32_t vis_gen, uint32_t live_vis);

int fold_weft_ok(uint32_t vis_gen, uint32_t live_vis) {
  return phase_mesh_ok(vis_gen, live_vis);
}
EOF

cat > "${root_dir}/vault_r/cord_phase.c" <<'EOF'
#include "plan_types.h"

int cord_phase_ok(uint32_t vis_gen, uint32_t live_vis) {
  return vis_gen == live_vis ? 1 : 0;
}
EOF

cat > "${root_dir}/vault_r/stamp_line.c" <<'EOF'
#include "plan_types.h"

int mark_fold_ok(uint32_t vis_gen, uint32_t live_vis);

int stamp_line_ok(uint32_t vis_gen, uint32_t live_vis, uint64_t row_est, int partial_req) {
  if (!partial_req) {
    return 1;
  }
  if (!mark_fold_ok(vis_gen, live_vis)) {
    return 0;
  }
  return row_est > 0 ? 1 : 0;
}
EOF

log "=== step 8: final hook and contract check ==="
"${root_dir}/ci/build_and_load.sh"

python3 - <<'PY'
import json
import os
from pathlib import Path

root = Path(os.environ.get("TASK_APP_ROOT", "/app"))
doc = json.loads((root / "output/plan_audit.json").read_text(encoding="utf-8"))
summary = doc["summary"]
assert summary["pair_mismatch_count"] == 0, summary
assert summary["step_mismatch_total"] == 0, summary
for row in doc["scenarios"]:
    if row["mode"] == "pause_resume":
        assert row["pair_ok"] is True, row
        assert row["stats_ok"] is True, row
    assert row["finish_reason"] == "ok", row
print("plan_audit contract ok", summary)
PY
