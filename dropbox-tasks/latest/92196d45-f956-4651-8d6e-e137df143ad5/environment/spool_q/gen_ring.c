#include "plan_types.h"

int ring_weft_ok(uint32_t memo_gen, uint32_t gen);

int gen_ring_ok(uint32_t memo_gen, uint32_t gen) {
  return ring_weft_ok(memo_gen, gen);
}
