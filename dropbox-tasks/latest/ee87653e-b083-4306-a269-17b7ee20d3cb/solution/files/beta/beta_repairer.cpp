#include "beta_repairer.hpp"
#include "elf_helper.hpp"
#include <iostream>
#include <vector>

namespace reloc {

bool repair_beta_section(const std::string& path, const Elf64_Shdr& shdr, uint32_t num_syms) {
    (void)num_syms; // unused parameter for now
    std::vector<uint8_t> data;
    if (!elf::read_section_data(path, shdr, data)) {
        return false;
    }

    if (data.size() % sizeof(Elf64_Rela) != 0) {
        std::cerr << "Error: Section size is not a multiple of Elf64_Rela" << std::endl;
        return false;
    }

    size_t num_entries = data.size() / sizeof(Elf64_Rela);
    Elf64_Rela* relocs = reinterpret_cast<Elf64_Rela*>(data.data());

    for (size_t i = 0; i < num_entries; ++i) {
        uint64_t r_info = relocs[i].r_info;
        uint32_t r_sym_scrambled = r_info >> 32;
        uint32_t r_type_scrambled = r_info & 0xFFFFFFFF;

        uint32_t r_sym = r_sym_scrambled ^ 0x2A3B4C5D;
        uint32_t r_type = r_type_scrambled ^ 0x7E;

        relocs[i].r_info = (static_cast<uint64_t>(r_sym) << 32) | r_type;
    }

    return elf::write_section_data(path, shdr, data);
}

} // namespace reloc
