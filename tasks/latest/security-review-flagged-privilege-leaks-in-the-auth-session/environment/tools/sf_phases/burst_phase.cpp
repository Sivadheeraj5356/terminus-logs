#include "burst_phase.hpp"

void burst_fold(nx_ctx *nx, uint32_t pid, int delta, uint64_t fence) {
  fold_cap_m(nx, pid, delta, fence);
}
