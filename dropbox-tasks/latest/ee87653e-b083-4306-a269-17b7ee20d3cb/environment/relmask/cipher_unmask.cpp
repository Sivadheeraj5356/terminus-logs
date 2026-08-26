#include "cipher_unmask.hpp"
#include "elf_helper.hpp"

namespace reloc {

bool unmask_cipher_beta_section(const std::string& path, const Elf64_Shdr& shdr, uint32_t num_syms) {
    (void)path;
    (void)shdr;
    (void)num_syms;
    return false;
}

} // namespace reloc
