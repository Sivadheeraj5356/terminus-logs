#include "plan_types.h"

int cord_ring_ok(uint32_t memo_gen, uint32_t gen);

int loop_mesh_ok(uint32_t memo_gen, uint32_t gen) {
  return cord_ring_ok(memo_gen, gen);
}
