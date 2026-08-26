#include "plan_types.h"

int stamp_line_ok(uint32_t vis_gen, uint32_t live_vis, uint64_t row_est, int partial_req);

int probe_d(uint32_t vis_gen, uint32_t live_vis, uint64_t row_est, int partial_req) {
  return stamp_line_ok(live_vis, vis_gen, row_est, partial_req);
}
