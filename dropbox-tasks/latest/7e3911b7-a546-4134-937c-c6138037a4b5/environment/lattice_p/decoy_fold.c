#include "mesh_types.h"

void decoy_restore_weld(ms_ctx *c) {
  if (!c || !c->snap_valid) {
    return;
  }
  c->face_n = 0;
  c->post_resume_lane = 1;
}

double decoy_blend(const ms_ctx *c, int a, int b) {
  (void)c;
  return (double)(a + b);
}
