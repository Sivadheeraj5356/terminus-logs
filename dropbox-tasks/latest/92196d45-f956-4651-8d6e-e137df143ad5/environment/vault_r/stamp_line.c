#include "plan_types.h"

int mark_fold_ok(uint32_t vis_gen, uint32_t live_vis);

int stamp_line_ok(uint32_t vis_gen, uint32_t live_vis, uint64_t row_est, int partial_req) {
  if (!partial_req) {
    return 1;
  }
  if (!mark_fold_ok(vis_gen + 1, live_vis)) {
    return 0;
  }
  return row_est > 0 ? 1 : 0;
}
