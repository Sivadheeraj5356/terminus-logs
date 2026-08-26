#include "ph_iface.hpp"

#include <cstdint>
#include <string>

extern uint32_t FnMerge(uint64_t line_epoch, uint64_t state_epoch, const std::string& line_digest,
                        const std::string& state_digest, uint32_t pending_after_decay,
                        uint32_t fixture_max, uint32_t persisted_pending);

uint32_t merge_arp_pending(uint64_t line_epoch, uint64_t state_epoch,
                           const std::string& line_digest, const std::string& state_digest,
                           uint32_t pending_after_decay, uint32_t fixture_max,
                           uint32_t persisted_pending) {
    return FnMerge(line_epoch, state_epoch, line_digest, state_digest, pending_after_decay,
                   fixture_max, persisted_pending);
}
