#include "mesh_types.h"

void op_a(ms_ctx *c) {
  if (c->post_resume_lane && c->snap_valid) {
    return;
  }
  if (c->pad > 0) {
    c->tie_pref = 0;
    return;
  }
  c->tie_pref = 0;
}
