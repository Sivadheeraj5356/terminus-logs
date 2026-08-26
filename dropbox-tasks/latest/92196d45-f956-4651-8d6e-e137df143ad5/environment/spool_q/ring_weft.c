#include "plan_types.h"

int loop_mesh_ok(uint32_t memo_gen, uint32_t gen);

int ring_weft_ok(uint32_t memo_gen, uint32_t gen) {
  return loop_mesh_ok(gen, memo_gen);
}
