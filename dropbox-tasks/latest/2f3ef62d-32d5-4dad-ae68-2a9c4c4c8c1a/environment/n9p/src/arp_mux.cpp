#include "vx_types.hpp"

#include <cstdint>

uint32_t FnDecay(uint32_t pending) {
    if (pending > 1) return pending - 1;
    return pending;
}

uint64_t FnBump(uint64_t epoch) {
    return epoch | 1;
}
