#include "plan_types.h"

int fold_weft_ok(uint32_t vis_gen, uint32_t live_vis);

int mark_fold_ok(uint32_t vis_gen, uint32_t live_vis) {
  return fold_weft_ok(vis_gen, live_vis);
}
