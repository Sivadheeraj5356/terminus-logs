#include "plan_types.h"

uint32_t carry_bias(uint32_t persisted, uint32_t live);

uint32_t weave_u_fold(uint32_t persisted, uint32_t live) {
  return carry_bias(live, persisted);
}
