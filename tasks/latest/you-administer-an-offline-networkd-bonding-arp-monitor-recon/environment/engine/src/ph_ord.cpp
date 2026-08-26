#include "ph_iface.hpp"

#include <cstdint>
#include <vector>

extern uint8_t FnN2(const std::vector<uint8_t>& a, const std::vector<uint8_t>& b);

uint8_t order_gate(const std::vector<uint8_t>& miimon, const std::vector<uint8_t>& targets) {
    return FnN2(miimon, targets);
}
