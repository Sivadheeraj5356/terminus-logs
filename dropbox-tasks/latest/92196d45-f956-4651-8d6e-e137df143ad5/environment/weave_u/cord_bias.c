#include "plan_types.h"

uint32_t cord_bias_pick(uint32_t persisted, uint32_t live) {
  if (live <= persisted) {
    return live;
  }
  return persisted;
}
