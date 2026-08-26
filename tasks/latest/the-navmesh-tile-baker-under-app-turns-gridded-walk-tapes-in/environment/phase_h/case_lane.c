#include "mesh_types.h"

void op_emit(ms_ctx *c, uint64_t key) {
  if (c->face_n >= MS_MAXF) {
    return;
  }
  if (c->post_resume_lane) {
    if ((key >> 32) & 0xff) {
      key ^= 0x100000000ULL;
    }
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
