#!/usr/bin/env bash
set -euo pipefail

root_dir="${TASK_APP_ROOT:-/app}"
cd "${root_dir}"

cat > "${root_dir}/phase_h/case_lane.c" <<'EOF'
#include "mesh_types.h"

void op_emit(ms_ctx *c, uint64_t key) {
  if (c->face_n >= MS_MAXF) {
    return;
  }
  c->faces[c->face_n++] = key;
}

uint64_t tie_flip_key(int ax, int ay, int az, int bx, int by, int bz) {
  if (ax > bx || (ax == bx && ay > by) || (ax == bx && ay == by && az > bz)) {
    int tx = ax, ty = ay, tz = az;
    ax = bx;
    ay = by;
    az = bz;
    bx = tx;
    by = ty;
    bz = tz;
  }
  return ((uint64_t)(uint32_t)ax << 40) | ((uint64_t)(uint32_t)ay << 24) | ((uint64_t)(uint32_t)az << 8) | (uint64_t)(uint32_t)bx;
}
EOF

cat > "${root_dir}/phase_h/restore_lane.c" <<'EOF'
#include "mesh_types.h"

#include <stdlib.h>

static int cmp_u64(const void *a, const void *b) {
  const uint64_t ua = *(const uint64_t *)a;
  const uint64_t ub = *(const uint64_t *)b;
  if (ua < ub) {
    return -1;
  }
  if (ua > ub) {
    return 1;
  }
  return 0;
}

void phase_b(ms_ctx *c) {
  if (!c->snap_valid || !c->resume_pending) {
    return;
  }
  c->face_n = c->snap_face_n;
  for (int i = 0; i < c->face_n; i++) {
    c->faces[i] = c->snap_faces[i];
  }
  qsort(c->faces, (size_t)c->face_n, sizeof(c->faces[0]), cmp_u64);
  c->z_cursor = c->snap_z_cursor;
  c->slab_z_base = c->snap_slab_z_base;
}
EOF

cat > "${root_dir}/stencil_k/edge_table.c" <<'EOF'
#include "mesh_types.h"

void op_a(ms_ctx *c) {
  c->tie_pref = (c->pad > 0) ? 1 : 0;
}
EOF

cat > "${root_dir}/stencil_k/weld_fold.c" <<'EOF'
#include "mesh_types.h"

void op_a(ms_ctx *c);

void resolve_c(ms_ctx *c) {
  if (!c->snap_valid || !c->resume_pending) {
    return;
  }
  if (c->pad != c->snap_pad) {
    op_a(c);
    return;
  }
  c->tie_pref = c->snap_tie_pref;
  c->slab_z_base = c->snap_slab_z_base;
}
EOF

cat > "${root_dir}/crate_q/slab_pack.c" <<'EOF'
#include "mesh_types.h"

#include <string.h>

void op_a(ms_ctx *c);
void op_emit(ms_ctx *c, uint64_t key);
uint64_t tie_flip_key(int ax, int ay, int az, int bx, int by, int bz);

void ms_reset(ms_ctx *c) {
  memset(c, 0, sizeof(*c));
  c->tie_pref = 0;
}

static uint64_t pack_face(int x, int y, int z, int dir, int slab_base) {
  (void)slab_base;
  return ((uint64_t)(uint32_t)x << 32) | ((uint64_t)(uint32_t)y << 16) | ((uint64_t)(uint16_t)z << 4) | (uint64_t)(dir & 0xf);
}

static void emit_cell_faces(ms_ctx *c, int x, int y, int z) {
  static const int dx[6] = {1, -1, 0, 0, 0, 0};
  static const int dy[6] = {0, 0, 1, -1, 0, 0};
  static const int dz[6] = {0, 0, 0, 0, 1, -1};
  int inside = ms_inside(c, x, y, z);
  for (int k = 0; k < 6; k++) {
    int nx = x + dx[k];
    int ny = y + dy[k];
    int nz = z + dz[k];
    int out = ms_inside(c, nx, ny, nz);
    if (inside == out) {
      continue;
    }
    uint64_t fk = pack_face(x, y, z, k, c->slab_z_base);
    if (c->field[ms_idx(c, x, y, z)] == c->iso) {
      uint64_t tk = tie_flip_key(x, y, z, nx, ny, nz);
      if ((tk & 1ULL) != 0) {
        fk ^= 0x100000000ULL;
      }
    }
    op_emit(c, fk);
  }
}

void drive_slab(ms_ctx *c, int z_end) {
  if (z_end > c->nz) {
    z_end = c->nz;
  }
  op_a(c);
  for (int z = c->z_cursor; z < z_end; z++) {
    for (int y = 0; y < c->ny; y++) {
      for (int x = 0; x < c->nx; x++) {
        emit_cell_faces(c, x, y, z);
      }
    }
  }
  c->z_cursor = z_end;
}
EOF

cat > "${root_dir}/crate_q/snap_fold.c" <<'EOF'
#include "mesh_types.h"

#include <string.h>

void resolve_c(ms_ctx *c);
void phase_b(ms_ctx *c);

void step_1(ms_ctx *c) {
  c->snap_valid = 1;
  c->snap_z_cursor = c->z_cursor;
  c->snap_slab_z_base = c->slab_z_base;
  c->snap_pad = c->pad;
  c->snap_tie_pref = c->tie_pref;
  c->snap_face_n = c->face_n;
  memcpy(c->snap_faces, c->faces, sizeof(c->faces[0]) * (size_t)c->face_n);
}

void step_2(ms_ctx *c) {
  if (!c->snap_valid) {
    return;
  }
  c->resume_pending = 1;
}

void gx_checkpoint(ms_ctx *c) {
  step_1(c);
}

void gx_resume(ms_ctx *c) {
  if (!c->snap_valid) {
    return;
  }
  step_2(c);
  resolve_c(c);
  phase_b(c);
  c->resume_pending = 0;
  c->post_resume_lane = 0;
}
EOF

"${root_dir}/ci/build_and_load.sh"

test -s "${root_dir}/output/nav_audit.json"

python3 - <<'PY'
import json
import os
import sys

report = os.path.join(os.environ.get("TASK_APP_ROOT", "/app"), "output", "nav_audit.json")
doc = json.load(open(report, encoding="utf-8"))
if doc.get("summary", {}).get("pair_mismatch_count") != 0:
    sys.exit("oracle: pair mismatches remain")
for row in doc.get("scenarios", []):
    if not row.get("pair_ok"):
        sys.exit(f"oracle: pair_ok false for {row['scenario_id']} {row['mode']}")
    if not row.get("link_ok"):
        sys.exit(f"oracle: link_ok false for {row['scenario_id']} {row['mode']}")
    if not row.get("area_overlay_ok"):
        sys.exit(f"oracle: area_overlay_ok false for {row['scenario_id']} {row['mode']}")
PY
