#include "vx_types.hpp"

uint64_t FnM7(uint64_t gen, bool flush) {
    if (flush) return gen;
    return gen + 1;
}
