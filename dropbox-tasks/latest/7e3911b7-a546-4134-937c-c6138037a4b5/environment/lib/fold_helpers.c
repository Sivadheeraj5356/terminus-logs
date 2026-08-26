#include "mesh_types.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

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

void fold_nav_digest(const ms_ctx *c, char *out, size_t out_len) {
  uint64_t tmp[MS_MAXF];
  int n = c->face_n;
  if (n > MS_MAXF) {
    n = MS_MAXF;
  }
  memcpy(tmp, c->faces, sizeof(uint64_t) * (size_t)n);
  qsort(tmp, (size_t)n, sizeof(tmp[0]), cmp_u64);
  unsigned long long mix = 1469598103934665603ULL;
  for (int i = 0; i < n; i++) {
    mix ^= tmp[i];
    mix *= 1099511628211ULL;
  }
  snprintf(out, out_len, "%016llx", mix);
}

int fold_border_weld_count(const ms_ctx *c) {
  if (c->face_n <= 0) {
    return 0;
  }
  uint64_t tmp[MS_MAXF];
  int n = c->face_n;
  memcpy(tmp, c->faces, sizeof(uint64_t) * (size_t)n);
  qsort(tmp, (size_t)n, sizeof(tmp[0]), cmp_u64);
  int uniq = 1;
  for (int i = 1; i < n; i++) {
    if (tmp[i] != tmp[i - 1]) {
      uniq++;
    }
  }
  return uniq;
}


void fold_link_digest(const ms_ctx *c, char *out, size_t out_len) {
  uint64_t tmp[MS_MAXF];
  int n = c->face_n;
  if (n > MS_MAXF) {
    n = MS_MAXF;
  }
  memcpy(tmp, c->faces, sizeof(uint64_t) * (size_t)n);
  qsort(tmp, (size_t)n, sizeof(tmp[0]), cmp_u64);
  unsigned long long mix = 0xcbf29ce484222325ULL ^ (unsigned long long)n;
  for (int i = 0; i < n; i++) {
    mix ^= tmp[i] ^ ((unsigned long long)(i + 1) << 11);
    mix *= 1099511628211ULL;
  }
  snprintf(out, out_len, "%016llx", mix);
}

int fold_link_ok(const ms_ctx *c) {
  if (c->face_n <= 0) {
    return 0;
  }
  if (c->seam_open_count > 0) {
    return 0;
  }
  return 1;
}
