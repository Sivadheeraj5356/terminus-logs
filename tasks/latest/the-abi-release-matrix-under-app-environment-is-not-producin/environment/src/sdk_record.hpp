#ifndef SDK_RECORD_HPP
#define SDK_RECORD_HPP

#include <cstdint>

#include "generated/sdk.hpp"

// The on-wire SDK record. The frozen v1 prefix (slots 0-11) is always present;
// the extension groups are compiled in only when the active lane selects them.
// Physical member order matches the generator's pack order.
struct sdk_record {
    uint32_t abi_version;
    const char *name;
    uint64_t checksum;
    void *dispatch;
    uint32_t reserved;
    uint64_t capability_mask;
    uint64_t lifecycle_epoch;
    void *allocator_cookie;
    uint32_t config_crc;
    void *telemetry_sink;
    const char *quarantine_tag;
    uint32_t runtime_flags;
#if SDK_HAS_OBSERVABILITY
    uint64_t telemetry_epoch;
    uint32_t sample_stride;
#endif
#if SDK_HAS_DIAGNOSTICS
    void *diagnostic_ring;
    uint32_t fault_budget;
#endif
#if SDK_HAS_RECOVERY
    uint64_t recovery_cookie;
    uint32_t quarantine_depth;
#endif
};

#endif
