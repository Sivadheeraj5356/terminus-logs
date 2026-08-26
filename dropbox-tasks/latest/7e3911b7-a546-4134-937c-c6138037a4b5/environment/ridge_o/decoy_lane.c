#include "mesh_types.h"

void phase_b_decoy(ms_ctx *c) {
  if (!c) {
    return;
  }
  c->face_n = 0;
}

int decoy_rank(const ms_ctx *c, int cell) {
  return c ? cell % 7 : 0;
}
