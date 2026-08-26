#include "plan_types.h"

int reel_m_drum_slot(uint32_t memo_gen, uint32_t gen) {
  return memo_gen == gen ? 1 : 0;
}

int reel_m_phase_ok(uint32_t vis_gen, uint32_t live_vis) {
  return vis_gen == live_vis ? 1 : 0;
}
