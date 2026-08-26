#include "toolchain_detector.hpp"
#include "elf_helper.hpp"
#include <cstring>
#include <vector>

namespace reloc {

ToolchainType detect_toolchain(const std::string& path) {
    Elf64_Ehdr ehdr;
    if (!elf::read_elf_header(path, ehdr)) {
        return ToolchainType::UNKNOWN;
    }

    std::vector<Elf64_Shdr> shdrs;
    if (!elf::read_section_headers(path, ehdr, shdrs)) {
        return ToolchainType::UNKNOWN;
    }

    std::vector<char> shstrtab;
    if (!elf::read_section_names(path, ehdr, shdrs, shstrtab)) {
        return ToolchainType::UNKNOWN;
    }

    // Find .dynsym to get the number of symbols
    int dynsym_idx = elf::find_section_by_name(".dynsym", shdrs, shstrtab);
    uint32_t num_syms = 0;
    if (dynsym_idx != -1) {
        num_syms = shdrs[dynsym_idx].sh_size / sizeof(Elf64_Sym);
    }

    // Locate .rela.dyn or .rela.plt
    int rela_dyn_idx = elf::find_section_by_name(".rela.dyn", shdrs, shstrtab);
    int rela_plt_idx = elf::find_section_by_name(".rela.plt", shdrs, shstrtab);

    int target_idx = (rela_dyn_idx != -1) ? rela_dyn_idx : rela_plt_idx;
    if (target_idx == -1) {
        return ToolchainType::ALPHA; // No dynamic relocation sections, treat as standard
    }

    std::vector<uint8_t> data;
    if (!elf::read_section_data(path, shdrs[target_idx], data)) {
        return ToolchainType::UNKNOWN;
    }

    if (data.size() >= 8) {
        uint32_t magic = 0;
        std::memcpy(&magic, data.data(), 4);
        if (magic == 0x474D524C) { // "GMRL"
            return ToolchainType::GAMMA;
        }
    }

    // Check for BETA by inspecting relocation entries
    if (data.size() >= sizeof(Elf64_Rela)) {
        size_t num_relocs = data.size() / sizeof(Elf64_Rela);
        const Elf64_Rela* relocs = reinterpret_cast<const Elf64_Rela*>(data.data());
        for (size_t i = 0; i < num_relocs; ++i) {
            uint64_t r_info = relocs[i].r_info;
            uint32_t r_type = r_info & 0xFFFFFFFF;
            uint32_t r_sym = r_info >> 32;
            if (r_type > 42 || (num_syms > 0 && r_sym >= num_syms)) {
                return ToolchainType::BETA;
            }
        }
    }

    return ToolchainType::ALPHA;
}

} // namespace reloc
