#include "plan_types.h"

int cord_lane_bucket(int pred_bucket, int use_snap);

int drum_mesh_bucket(int pred_bucket, int use_snap) {
  return cord_lane_bucket(pred_bucket, use_snap);
}
