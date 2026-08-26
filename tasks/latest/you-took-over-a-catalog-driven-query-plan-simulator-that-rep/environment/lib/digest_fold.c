#include "digest_fold.h"
#include "plan_types.h"

#include <stdio.h>
#include <string.h>

void fold_hex(const char *a, const char *b, const char *c, uint32_t gen, char *out, size_t out_len) {
  unsigned long acc = 2166136261UL ^ (unsigned long)gen;
  const char *parts[3] = {a, b, c};
  for (int i = 0; i < 3; i++) {
    const char *p = parts[i] ? parts[i] : "";
    while (*p) {
      acc = (acc * 131UL) ^ (unsigned char)*p++;
    }
  }
  snprintf(out, out_len, "%016lx", acc & 0xffffffffffffffffUL);
}

void plan_digest_row(const pl_row *row, char *out, size_t out_len) {
  fold_hex(row->step_alpha_id, row->step_beta_id, row->step_gamma_id, row->stats_gen, out, out_len);
}
