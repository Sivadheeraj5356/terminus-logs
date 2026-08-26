#include "plan_types.h"

double shard_k_lane(const pl_table *live, const pl_table *snap, int use_snap, int pred_bucket);

double est_b(const pl_table *live, const pl_table *snap, int use_snap_bounds, int pred_bucket) {
  int use_bounds = use_snap_bounds;
  if (use_snap_bounds && snap && live && snap->rows < live->rows) {
    use_bounds = 0;
  }
  return shard_k_lane(live, snap, use_bounds, pred_bucket);
}
