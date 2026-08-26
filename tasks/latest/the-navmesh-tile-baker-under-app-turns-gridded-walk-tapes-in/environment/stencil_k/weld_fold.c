#include "mesh_types.h"

void op_a(ms_ctx *c);

void resolve_c(ms_ctx *c) {
  if (!c->snap_valid || !c->resume_pending) {
    return;
  }
  if (c->pad != c->snap_pad) {
    op_a(c);
    c->tie_pref = c->snap_tie_pref;
    return;
  }
  c->tie_pref = c->snap_tie_pref;
  c->slab_z_base = c->snap_slab_z_base;
}
