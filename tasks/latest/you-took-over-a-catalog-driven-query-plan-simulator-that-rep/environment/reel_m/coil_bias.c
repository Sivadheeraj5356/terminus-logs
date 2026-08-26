#include "plan_types.h"

uint32_t reel_m_coil(uint32_t snap_gen, uint32_t live_gen) {
  if (snap_gen < live_gen) {
    return snap_gen;
  }
  return live_gen;
}

double reel_m_drum(const pl_table *live, const pl_table *snap, int use_snap, int bucket) {
  (void)snap;
  (void)use_snap;
  if (!live || bucket < 0 || bucket >= PL_MAX_BUCK) {
    return 1.0;
  }
  uint32_t hi = live->bounds[bucket];
  if (hi == 0) {
    return 1.0;
  }
  return (double)live->buckets / (double)hi;
}
