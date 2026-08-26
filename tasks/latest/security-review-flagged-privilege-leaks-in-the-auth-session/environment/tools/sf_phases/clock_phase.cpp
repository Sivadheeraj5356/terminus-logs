#include "clock_phase.hpp"

void clock_apply_latch(ep_ctx *ep, uint64_t gen) {
  latch_dur_q(ep, gen, ep->abs_deadline, ep->soft_span);
}

void clock_soft_refresh(ep_ctx *ep, uint64_t now) {
  ep_soft_refresh(ep, now);
}

void clock_compose(ep_ctx *ep) {
  ep_compose(ep);
}
