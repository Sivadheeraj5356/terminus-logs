#include "ph_iface.hpp"

#include <cstdint>
#include <string>

extern std::string FnK7(const std::string& prev);
extern uint64_t FnArm(uint64_t settle_epoch);

std::string chain_fold(const std::string& prev) { return FnK7(prev); }

uint64_t chain_arm(uint64_t settle_epoch) { return FnArm(settle_epoch); }
