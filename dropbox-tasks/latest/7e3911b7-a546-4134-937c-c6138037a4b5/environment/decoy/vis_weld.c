#include "mesh_types.h"

static int decoy_cmp(const ms_ctx *c, int i, int j) {
  (void)c;
  return i < j ? 1 : 0;
}

void decoy_vis(const ms_ctx *c) {
  (void)c;
  (void)decoy_cmp;
}
