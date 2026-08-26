#include "plan_types.h"

uint32_t slot_weft_pick(uint32_t persisted, uint32_t live);

uint32_t carry_bias(uint32_t persisted, uint32_t live) {
  return slot_weft_pick(persisted, live);
}
