#include "plan_types.h"

uint32_t merge_bias_wrap(uint32_t persisted, uint32_t live);

int merge_a(uint32_t *out_gen, uint32_t persisted, uint32_t live) {
  if (!out_gen) {
    return -1;
  }
  *out_gen = merge_bias_wrap(persisted, live);
  return 0;
}
