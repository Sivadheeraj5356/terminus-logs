#include <cstddef>
#include <cstdint>
#include <cstdio>

#include "sdk_record.hpp"

namespace {

int g_slot = 0;
bool g_first = true;

void emit(const char *name, const char *ctype, std::size_t offset, std::size_t size) {
    if (!g_first) {
        std::fputs(",", stdout);
    }
    g_first = false;
    std::printf("{\"slot\":%d,\"name\":\"%s\",\"ctype\":\"%s\",\"offset\":%zu,\"size\":%zu}",
                g_slot++, name, ctype, offset, size);
}

}  // namespace

int main() {
    std::printf("{\"lane\":\"%s\",\"record_size\":%zu,\"align\":%zu,\"field_count\":%d,\"fields\":[",
                SDK_LANE, sizeof(sdk_record), alignof(sdk_record), SDK_FIELD_COUNT);

    emit("abi_version", "uint32_t", offsetof(sdk_record, abi_version), sizeof(sdk_record::abi_version));
    emit("name", "const char*", offsetof(sdk_record, name), sizeof(sdk_record::name));
    emit("checksum", "uint64_t", offsetof(sdk_record, checksum), sizeof(sdk_record::checksum));
    emit("dispatch", "void*", offsetof(sdk_record, dispatch), sizeof(sdk_record::dispatch));
    emit("reserved", "uint32_t", offsetof(sdk_record, reserved), sizeof(sdk_record::reserved));
    emit("capability_mask", "uint64_t", offsetof(sdk_record, capability_mask), sizeof(sdk_record::capability_mask));
    emit("lifecycle_epoch", "uint64_t", offsetof(sdk_record, lifecycle_epoch), sizeof(sdk_record::lifecycle_epoch));
    emit("allocator_cookie", "void*", offsetof(sdk_record, allocator_cookie), sizeof(sdk_record::allocator_cookie));
    emit("config_crc", "uint32_t", offsetof(sdk_record, config_crc), sizeof(sdk_record::config_crc));
    emit("telemetry_sink", "void*", offsetof(sdk_record, telemetry_sink), sizeof(sdk_record::telemetry_sink));
    emit("quarantine_tag", "const char*", offsetof(sdk_record, quarantine_tag), sizeof(sdk_record::quarantine_tag));
    emit("runtime_flags", "uint32_t", offsetof(sdk_record, runtime_flags), sizeof(sdk_record::runtime_flags));
#if SDK_HAS_OBSERVABILITY
    emit("telemetry_epoch", "uint64_t", offsetof(sdk_record, telemetry_epoch), sizeof(sdk_record::telemetry_epoch));
    emit("sample_stride", "uint32_t", offsetof(sdk_record, sample_stride), sizeof(sdk_record::sample_stride));
#endif
#if SDK_HAS_DIAGNOSTICS
    emit("diagnostic_ring", "void*", offsetof(sdk_record, diagnostic_ring), sizeof(sdk_record::diagnostic_ring));
    emit("fault_budget", "uint32_t", offsetof(sdk_record, fault_budget), sizeof(sdk_record::fault_budget));
#endif
#if SDK_HAS_RECOVERY
    emit("recovery_cookie", "uint64_t", offsetof(sdk_record, recovery_cookie), sizeof(sdk_record::recovery_cookie));
    emit("quarantine_depth", "uint32_t", offsetof(sdk_record, quarantine_depth), sizeof(sdk_record::quarantine_depth));
#endif

    std::printf("]}\n");
    return 0;
}
