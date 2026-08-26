#include "encoding_probe.hpp"
#include "elf_helper.hpp"

namespace reloc {

EncodingProfile probe_encoding_profile(const std::string& path) {
    (void)path;
    return EncodingProfile::UNKNOWN;
}

} // namespace reloc
