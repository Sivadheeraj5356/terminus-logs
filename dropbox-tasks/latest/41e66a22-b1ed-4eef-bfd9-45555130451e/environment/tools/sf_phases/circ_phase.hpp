#pragma once
#include "../../core/kz/ring.hpp"
#include "../../lane/ep/latch.hpp"
#include <cstdint>
#include <string>

void circ_apply_seal(kz_ctx *kz, uint64_t gen, const std::string &cred);
void circ_apply_latch(ep_ctx *ep, uint64_t gen);
