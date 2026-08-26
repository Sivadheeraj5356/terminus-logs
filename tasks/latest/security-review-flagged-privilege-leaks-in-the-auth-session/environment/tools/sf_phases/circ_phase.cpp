#include "circ_phase.hpp"

void circ_apply_seal(kz_ctx *kz, uint64_t gen, const std::string &cred) {
  seal_ring_v(kz, gen, reinterpret_cast<const uint8_t *>(cred.data()), cred.size());
}

void circ_apply_latch(ep_ctx *ep, uint64_t gen) {
  latch_dur_q(ep, gen, ep->abs_deadline, ep->soft_span);
}
