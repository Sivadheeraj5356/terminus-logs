#include "envelope_unpack.hpp"
#include "elf_helper.hpp"

namespace reloc {

bool unpack_envelope_gamma_section(const std::string& path, const Elf64_Shdr& shdr) {
    (void)path;
    (void)shdr;
    return false;
}

} // namespace reloc
