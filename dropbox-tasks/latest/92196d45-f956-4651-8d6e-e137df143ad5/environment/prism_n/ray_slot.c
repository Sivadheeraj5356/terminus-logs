#include "plan_types.h"

uint32_t prism_n_ray(uint32_t a, uint32_t b) {
  return a > b ? b : a;
}

int prism_n_phase(uint32_t memo_gen, uint32_t gen) {
  if (memo_gen <= gen) {
    return 1;
  }
  return 0;
}
