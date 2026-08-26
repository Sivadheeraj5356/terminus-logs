#ifndef MESH_TYPES_H
#define MESH_TYPES_H

#include <stddef.h>
#include <stdint.h>

#define MS_MAX 4096
#define MS_MAXW 20
#define MS_MAXH 20
#define MS_MAXD 20
#define MS_MAXF 8192

typedef struct {
  int nx;
  int ny;
  int nz;
  uint16_t iso;
  int pad;
  uint16_t field[MS_MAX];
  int z_cursor;
  int slab_z_base;
  uint64_t faces[MS_MAXF];
  int face_n;
  int snap_valid;
  int snap_z_cursor;
  int snap_slab_z_base;
  int snap_pad;
  int snap_tie_pref;
  uint64_t snap_faces[MS_MAXF];
  int snap_face_n;
  int resume_pending;
  int post_resume_lane;
  int tie_pref;
  int seam_open_count;
} ms_ctx;

typedef struct {
  char scenario_id[64];
  char mode[16];
  int polygon_count;
  int border_weld_count;
  char nav_digest[17];
  int portal_count;
  char link_digest[17];
  int link_ok;
  int area_overlay_ok;
  int seam_open_count;
  int pair_ok;
  char finish_reason[8];
} ms_row;

static inline int ms_idx(const ms_ctx *c, int x, int y, int z) {
  return z * c->nx * c->ny + y * c->nx + x;
}

static inline int ms_inside(const ms_ctx *c, int x, int y, int z) {
  if (x < 0 || y < 0 || z < 0 || x >= c->nx || y >= c->ny || z >= c->nz) {
    return 0;
  }
  uint16_t v = c->field[ms_idx(c, x, y, z)];
  if (v > c->iso) {
    return 1;
  }
  if (v < c->iso) {
    return 0;
  }
  return c->tie_pref;
}

void ms_reset(ms_ctx *c);
void fold_nav_digest(const ms_ctx *c, char *out, size_t out_len);
void fold_link_digest(const ms_ctx *c, char *out, size_t out_len);
int fold_link_ok(const ms_ctx *c);
int fold_border_weld_count(const ms_ctx *c);

#endif
