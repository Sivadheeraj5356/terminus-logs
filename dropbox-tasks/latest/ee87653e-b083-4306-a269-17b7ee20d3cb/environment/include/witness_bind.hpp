#ifndef WITNESS_BIND_HPP
#define WITNESS_BIND_HPP

#include <string>

namespace reloc {

enum class EncodingProfile {
    UNKNOWN,
    ALPHA,
    BETA,
    GAMMA
};

bool bind_relocation_witness(const std::string& path);

} // namespace reloc

#endif
