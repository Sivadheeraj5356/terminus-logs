#include "plan_types.h"

uint32_t coil_mesh_pick(uint32_t persisted, uint32_t live);

uint32_t slot_weft_pick(uint32_t persisted, uint32_t live) {
  return coil_mesh_pick(live, persisted);
}
