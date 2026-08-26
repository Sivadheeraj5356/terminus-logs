#include "vx_types.hpp"

#include <string>
#include <vector>

static bool starts_with(const std::vector<uint8_t>& v, const std::string& p) {
    if (v.size() < p.size()) return false;
    for (size_t i = 0; i < p.size(); ++i) {
        if (static_cast<char>(v[i]) != p[i]) return false;
    }
    return true;
}

uint8_t FnN2(const std::vector<uint8_t>& a, const std::vector<uint8_t>& b) {
    return (starts_with(a, "T1|") && starts_with(b, "M0|")) ? 1 : 0;
}
