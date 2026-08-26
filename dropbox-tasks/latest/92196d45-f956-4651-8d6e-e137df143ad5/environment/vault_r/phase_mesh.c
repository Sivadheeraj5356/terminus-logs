#include "plan_types.h"

int cord_phase_ok(uint32_t vis_gen, uint32_t live_vis);

int phase_mesh_ok(uint32_t vis_gen, uint32_t live_vis) {
  return cord_phase_ok(vis_gen, live_vis);
}
