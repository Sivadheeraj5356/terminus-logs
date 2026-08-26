#include "engine/types.hpp"
#include "measure/accum.hpp"

void commit_span_fp(SimState& s, double fp_sample) {
  uint64_t chunk = static_cast<uint64_t>(fp_sample * 4096.0);
  chunk ^= s.orbit_crossings * 10007u;
  s.ledger_tail += chunk;
}
