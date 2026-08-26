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
    if (c->post_resume_lane && z == c->z_cursor && k >= 4) {
      c->seam_open_count++;
      continue;
    }
    uint64_t fk = pack_face(x, y, z, k, c->slab_z_base);
    if (c->pad > 0 && z == c->slab_z_base && (k & 1) == 0) {
      fk ^= 0x40000000ULL;
    }
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
