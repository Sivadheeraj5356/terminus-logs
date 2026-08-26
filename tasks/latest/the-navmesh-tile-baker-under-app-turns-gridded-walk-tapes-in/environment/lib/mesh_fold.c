#include "mesh_fold.h"
#include "harness_lane.h"

#include <stdio.h>

void op_a(ms_ctx *c);
void gx_checkpoint(ms_ctx *c);
void gx_resume(ms_ctx *c);

void nav_digest_row(const ms_ctx *c, char *out, size_t out_len) {
  fold_nav_digest(c, out, out_len);
}

void ms_sync_pad(ms_ctx *c) {
  op_a(c);
}

void ms_pause_leg(ms_ctx *c) {
  gx_checkpoint(c);
  gx_resume(c);
}
