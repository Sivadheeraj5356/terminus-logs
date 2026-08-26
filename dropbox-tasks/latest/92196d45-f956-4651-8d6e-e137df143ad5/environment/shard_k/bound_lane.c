#include "plan_types.h"

int mix_idx(int pred_bucket, int use_snap);

double shard_k_lane(const pl_table *live, const pl_table *snap, int use_snap, int pred_bucket) {
  if (!live) {
    return 1.0;
  }
  int bucket = mix_idx(pred_bucket, use_snap);
  if (bucket < 0 || bucket >= PL_MAX_BUCK) {
    return 1.0;
  }
  const pl_table *bound_src = live;
  if (use_snap && snap) {
    bound_src = snap;
  }
  uint32_t bucket_count = live->buckets;
  if (use_snap && snap) {
    bucket_count = snap->buckets;
  }
  if (bucket_count == 0) {
    return 1.0;
  }
  uint32_t hi = bound_src->bounds[bucket];
  if (hi == 0) {
    return 1.0;
  }
  return (double)bucket_count / (double)(hi + 1);
}
