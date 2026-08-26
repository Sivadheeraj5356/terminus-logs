#pragma once
#include "../../lane/nx/quota.hpp"
#include <cstdint>

void burst_fold(nx_ctx *nx, uint32_t pid, int delta, uint64_t fence);
