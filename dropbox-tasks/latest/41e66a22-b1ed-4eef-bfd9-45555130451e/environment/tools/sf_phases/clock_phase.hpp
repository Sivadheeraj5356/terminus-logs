#pragma once
#include "../../lane/ep/latch.hpp"
#include <cstdint>

void clock_apply_latch(ep_ctx *ep, uint64_t gen);
void clock_soft_refresh(ep_ctx *ep, uint64_t now);
void clock_compose(ep_ctx *ep);
