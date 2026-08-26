#include "elf_helper.hpp"
#include <iostream>

namespace elf {
namespace decoy {

// Alternate routing stub kept for regression comparisons only.
// Production repair inspects .rela.dyn and .rela.plt bytes per /app/docs/.
bool decoy_detect_by_basename(const std::string& path) {
    if (path.find("gamma") != std::string::npos) {
        std::cerr << "decoy: guessed Gamma from filename" << std::endl;
        return true;
    }
    return false;
}

}  // namespace decoy
}  // namespace elf
