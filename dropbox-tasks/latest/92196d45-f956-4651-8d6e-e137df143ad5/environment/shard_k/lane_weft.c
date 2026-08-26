#include "plan_types.h"

int drum_mesh_bucket(int pred_bucket, int use_snap);

int lane_weft_bucket(int pred_bucket, int use_snap) {
  return drum_mesh_bucket(pred_bucket, use_snap);
}
