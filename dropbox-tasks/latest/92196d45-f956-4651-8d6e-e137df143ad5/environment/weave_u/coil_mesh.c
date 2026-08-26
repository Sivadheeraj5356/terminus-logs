#include "plan_types.h"

uint32_t cord_bias_pick(uint32_t persisted, uint32_t live);

uint32_t coil_mesh_pick(uint32_t persisted, uint32_t live) {
  return cord_bias_pick(persisted, live);
}
