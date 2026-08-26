#include "ph_iface.hpp"

#include <cstdint>

extern uint32_t FnDecay(uint32_t pending);
extern uint64_t FnBump(uint64_t epoch);

uint32_t decay_arp_once(uint32_t pending) { return FnDecay(pending); }

uint64_t bump_epoch(uint64_t epoch) { return FnBump(epoch); }
