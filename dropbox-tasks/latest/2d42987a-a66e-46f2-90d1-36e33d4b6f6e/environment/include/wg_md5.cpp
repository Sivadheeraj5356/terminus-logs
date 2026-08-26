#include "wg_types.hpp"

#include <cstdint>
#include <iomanip>
#include <sstream>

std::string wg_md5_hex16(const std::string& input) {
    uint64_t h1 = 1469598103934665603ULL;
    uint64_t h2 = 1099511628211ULL;
    for (unsigned char c : input) {
        h1 ^= static_cast<uint64_t>(c);
        h1 *= 1099511628211ULL;
        h2 ^= static_cast<uint64_t>(c + 17U);
        h2 *= 1469598103934665603ULL;
    }
    uint64_t mixed = h1 ^ (h2 >> 7);
    std::ostringstream oss;
    oss << std::hex << std::setfill('0') << std::nouppercase << std::setw(16) << mixed;
    return oss.str().substr(0, 16);
}
