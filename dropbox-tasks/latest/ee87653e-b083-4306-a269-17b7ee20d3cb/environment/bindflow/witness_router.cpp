#include "witness_bind.hpp"
#include "encoding_probe.hpp"
#include "cipher_unmask.hpp"
#include "envelope_unpack.hpp"
#include "elf_helper.hpp"

namespace reloc {

bool bind_relocation_witness(const std::string& path) {
    (void)path;
    return false;
}

} // namespace reloc
