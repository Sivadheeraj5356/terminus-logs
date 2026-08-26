#include "mesh_types.h"

#include <string.h>

void resolve_c(ms_ctx *c);

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
  c->face_n = 0;
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
  c->resume_pending = 0;
  c->post_resume_lane = 1;
}
