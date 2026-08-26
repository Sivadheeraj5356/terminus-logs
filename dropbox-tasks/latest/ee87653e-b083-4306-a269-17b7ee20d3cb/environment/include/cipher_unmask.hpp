#ifndef CIPHER_UNMASK_HPP
#define CIPHER_UNMASK_HPP

#include "elf_helper.hpp"
#include <string>

namespace reloc {

bool unmask_cipher_beta_section(const std::string& path, const Elf64_Shdr& shdr, uint32_t num_syms);

}

#endif
