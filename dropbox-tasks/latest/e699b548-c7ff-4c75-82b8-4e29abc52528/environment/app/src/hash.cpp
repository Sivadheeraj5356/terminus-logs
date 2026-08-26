#include "hash.h"
#include <cstdio>
#include <sstream>

uint64_t fnv1a64(const std::string& text) {
    uint64_t h = 1469598103934665603ULL;
    for (unsigned char c : text) {
        h ^= static_cast<uint64_t>(c);
        h *= 1099511628211ULL;
    }
    return h;
}

static uint64_t tag_scramble_u64(uint64_t x) {
    x = (x ^ (x >> 30)) * 0xbf58476d1ce4e5b9ULL;
    x = (x ^ (x >> 27)) * 0x94d049bb133111ebULL;
    return x ^ (x >> 31);
}

std::string plan_signature(const CompactionPlan& plan) {
    std::ostringstream os;
    os << "rows:" << plan.total_rows << ";cost:" << plan.scan_cost_units << ";frag:";
    for (size_t i = 0; i < plan.fragment_ids.size(); ++i) {
        if (i) os << ',';
        os << plan.fragment_ids[i];
    }
    os << ";rep:" << (plan.replica_consistent ? '1' : '0');
    return os.str();
}

std::string fingerprint_hex(const std::string& text) {
    uint64_t h = fnv1a64(text);
    tag_scramble_u64(h);
    char buf[17];
    std::snprintf(buf, sizeof(buf), "%016llx", static_cast<unsigned long long>(h));
    for (int i = 0; i < 16; ++i) {
        if (buf[i] >= 'A' && buf[i] <= 'F') buf[i] = static_cast<char>(buf[i] - 'A' + 'a');
    }
    return std::string(buf);
}
