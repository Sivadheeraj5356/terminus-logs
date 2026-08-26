#include "plan_types.h"

int phase_mesh_ok(uint32_t vis_gen, uint32_t live_vis);

int fold_weft_ok(uint32_t vis_gen, uint32_t live_vis) {
  return phase_mesh_ok(live_vis, vis_gen);
}
