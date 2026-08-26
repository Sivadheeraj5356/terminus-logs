#include "elf_helper.hpp"
#include <fstream>
#include <iostream>
#include <cstring>

namespace elf {

bool read_elf_header(const std::string& path, Elf64_Ehdr& ehdr) {
    std::ifstream f(path, std::ios::binary);
    if (!f.is_open()) {
        std::cerr << "Failed to open file: " << path << std::endl;
        return false;
    }
    f.read(reinterpret_cast<char*>(&ehdr), sizeof(ehdr));
    if (f.gcount() != sizeof(ehdr)) {
        std::cerr << "Failed to read ELF header from " << path << std::endl;
        return false;
    }
    // Verify ELF magic
    if (std::memcmp(ehdr.e_ident, ELFMAG, SELFMAG) != 0) {
        std::cerr << "Not a valid ELF file: " << path << std::endl;
        return false;
    }
    // Verify 64-bit
    if (ehdr.e_ident[EI_CLASS] != ELFCLASS64) {
        std::cerr << "Not a 64-bit ELF file: " << path << std::endl;
        return false;
    }
    return true;
}

bool read_section_headers(const std::string& path, const Elf64_Ehdr& ehdr, std::vector<Elf64_Shdr>& shdrs) {
    std::ifstream f(path, std::ios::binary);
    if (!f.is_open()) return false;
    f.seekg(ehdr.e_shoff);
    shdrs.resize(ehdr.e_shnum);
    f.read(reinterpret_cast<char*>(shdrs.data()), ehdr.e_shnum * sizeof(Elf64_Shdr));
    if (f.gcount() != static_cast<std::streamsize>(ehdr.e_shnum * sizeof(Elf64_Shdr))) {
        std::cerr << "Failed to read section headers" << std::endl;
        return false;
    }
    return true;
}

bool read_section_names(const std::string& path, const Elf64_Ehdr& ehdr, const std::vector<Elf64_Shdr>& shdrs, std::vector<char>& shstrtab) {
    if (ehdr.e_shstrndx >= shdrs.size()) {
        std::cerr << "Invalid e_shstrndx" << std::endl;
        return false;
    }
    const auto& shdr = shdrs[ehdr.e_shstrndx];
    std::ifstream f(path, std::ios::binary);
    if (!f.is_open()) return false;
    f.seekg(shdr.sh_offset);
    shstrtab.resize(shdr.sh_size);
    f.read(shstrtab.data(), shdr.sh_size);
    if (f.gcount() != static_cast<std::streamsize>(shdr.sh_size)) {
        std::cerr << "Failed to read section name table" << std::endl;
        return false;
    }
    return true;
}

int find_section_by_name(const std::string& name, const std::vector<Elf64_Shdr>& shdrs, const std::vector<char>& shstrtab) {
    for (size_t i = 0; i < shdrs.size(); ++i) {
        const auto& shdr = shdrs[i];
        if (shdr.sh_name >= shstrtab.size()) continue;
        const char* sname = &shstrtab[shdr.sh_name];
        if (name == sname) {
            return static_cast<int>(i);
        }
    }
    return -1;
}

bool read_section_data(const std::string& path, const Elf64_Shdr& shdr, std::vector<uint8_t>& data) {
    std::ifstream f(path, std::ios::binary);
    if (!f.is_open()) return false;
    f.seekg(shdr.sh_offset);
    data.resize(shdr.sh_size);
    f.read(reinterpret_cast<char*>(data.data()), shdr.sh_size);
    if (f.gcount() != static_cast<std::streamsize>(shdr.sh_size)) {
        std::cerr << "Failed to read section data from offset " << shdr.sh_offset << std::endl;
        return false;
    }
    return true;
}

bool write_section_data(const std::string& path, const Elf64_Shdr& shdr, const std::vector<uint8_t>& data) {
    if (data.size() > shdr.sh_size) {
        std::cerr << "Error: Attempting to write " << data.size() << " bytes into section of size " << shdr.sh_size << std::endl;
        return false;
    }
    // We open in in|out mode to write in-place without truncating the file
    std::fstream f(path, std::ios::in | std::ios::out | std::ios::binary);
    if (!f.is_open()) {
        std::cerr << "Failed to open file for writing: " << path << std::endl;
        return false;
    }
    f.seekp(shdr.sh_offset);
    f.write(reinterpret_cast<const char*>(data.data()), data.size());
    if (!f) {
        std::cerr << "Failed to write section data at offset " << shdr.sh_offset << std::endl;
        return false;
    }
    return true;
}

} // namespace elf
