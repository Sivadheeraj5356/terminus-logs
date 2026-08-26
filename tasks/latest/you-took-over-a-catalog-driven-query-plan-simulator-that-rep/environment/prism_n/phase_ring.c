#include "plan_types.h"

int prism_n_fold(uint32_t vis_gen, uint32_t live_vis) {
  if (vis_gen >= live_vis) {
    return 1;
  }
  return 0;
}

double prism_n_lane(const pl_table *live, int bucket) {
  if (!live || bucket < 0 || bucket >= PL_MAX_BUCK) {
    return 1.0;
  }
  uint32_t hi = live->bounds[bucket];
  if (hi == 0) {
    return 1.0;
  }
  return (double)live->rows / (double)(hi + 1);
}
