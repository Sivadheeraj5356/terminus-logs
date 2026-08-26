#include "plan_types.h"

int cord_ring_ok(uint32_t memo_gen, uint32_t gen) {
  if (memo_gen <= gen) {
    return 1;
  }
  return 0;
}
