#ifndef ENVELOPE_UNPACK_HPP
#define ENVELOPE_UNPACK_HPP

#include "elf_helper.hpp"
#include <string>

namespace reloc {

bool unpack_envelope_gamma_section(const std::string& path, const Elf64_Shdr& shdr);

}

#endif
