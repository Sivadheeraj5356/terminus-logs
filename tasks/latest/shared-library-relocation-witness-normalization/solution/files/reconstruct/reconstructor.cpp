#include "reconstructor.hpp"
#include "toolchain_detector.hpp"
#include "beta_repairer.hpp"
#include "gamma_repairer.hpp"
#include "elf_helper.hpp"
#include <iostream>
#include <vector>

namespace reloc {

bool repair_relocations(const std::string& path) {
    ToolchainType type = detect_toolchain(path);
    if (type == ToolchainType::UNKNOWN) {
        std::cerr << "Error: Unknown toolchain type" << std::endl;
        return false;
    }

    if (type == ToolchainType::ALPHA) {
        std::cout << "Library is already standard (Alpha). No repair needed." << std::endl;
        return true;
    }

    Elf64_Ehdr ehdr;
    if (!elf::read_elf_header(path, ehdr)) return false;

    std::vector<Elf64_Shdr> shdrs;
    if (!elf::read_section_headers(path, ehdr, shdrs)) return false;

    std::vector<char> shstrtab;
    if (!elf::read_section_names(path, ehdr, shdrs, shstrtab)) return false;

    // Find .dynsym to get number of symbols
    int dynsym_idx = elf::find_section_by_name(".dynsym", shdrs, shstrtab);
    uint32_t num_syms = 0;
    if (dynsym_idx != -1) {
        num_syms = shdrs[dynsym_idx].sh_size / sizeof(Elf64_Sym);
    }

    std::vector<std::string> target_sections = {".rela.dyn", ".rela.plt"};

    for (const auto& sec_name : target_sections) {
        int sec_idx = elf::find_section_by_name(sec_name, shdrs, shstrtab);
        if (sec_idx == -1) continue;

        const auto& shdr = shdrs[sec_idx];
        if (type == ToolchainType::BETA) {
            if (!repair_beta_section(path, shdr, num_syms)) {
                return false;
            }
        } else if (type == ToolchainType::GAMMA) {
            if (!repair_gamma_section(path, shdr)) {
                return false;
            }
        }
    }

    return true;
}

} // namespace reloc
