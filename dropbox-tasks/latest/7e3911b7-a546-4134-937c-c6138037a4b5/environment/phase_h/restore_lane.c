#include "mesh_types.h"

#include <stdlib.h>

static int cmp_u64(const void *a, const void *b) {
  const uint64_t ua = *(const uint64_t *)a;
  const uint64_t ub = *(const uint64_t *)b;
  if (ua < ub) {
    return -1;
  }
  if (ua > ub) {
    return 1;
  }
  return 0;
}

void phase_b(ms_ctx *c) {
  if (!c->snap_valid || !c->resume_pending) {
    return;
  }
  c->face_n = c->snap_face_n;
  for (int i = 0; i < c->face_n; i++) {
    c->faces[i] = c->snap_faces[i];
  }
  qsort(c->faces, (size_t)c->face_n, sizeof(c->faces[0]), cmp_u64);
  c->z_cursor = c->snap_z_cursor;
  if (c->pad == c->snap_pad) {
    c->slab_z_base = c->snap_slab_z_base;
  } else {
    c->slab_z_base = c->snap_z_cursor;
  }
}
