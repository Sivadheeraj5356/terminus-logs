#include "vx_types.hpp"

#include <cstdint>
#include <string>

std::string FnK7(const std::string& prev) {
    if (prev.empty()) return "";
    return std::string(prev.rbegin(), prev.rend());
}

uint64_t FnArm(uint64_t settle_epoch) {
    return settle_epoch;
}
