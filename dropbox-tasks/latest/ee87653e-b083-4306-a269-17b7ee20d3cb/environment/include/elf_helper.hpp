#pragma once

#include <elf.h>
#include <string>
#include <vector>
#include <cstdint>

namespace elf {

// Read the main ELF64 header from the file.
bool read_elf_header(const std::string& path, Elf64_Ehdr& ehdr);

// Read all section headers.
bool read_section_headers(const std::string& path, const Elf64_Ehdr& ehdr, std::vector<Elf64_Shdr>& shdrs);

// Read the section header string table.
bool read_section_names(const std::string& path, const Elf64_Ehdr& ehdr, const std::vector<Elf64_Shdr>& shdrs, std::vector<char>& shstrtab);

// Find the index of a section by its name. Returns -1 if not found.
int find_section_by_name(const std::string& name, const std::vector<Elf64_Shdr>& shdrs, const std::vector<char>& shstrtab);

// Read the raw bytes of a section.
bool read_section_data(const std::string& path, const Elf64_Shdr& shdr, std::vector<uint8_t>& data);

// Overwrite the raw bytes of a section in-place.
bool write_section_data(const std::string& path, const Elf64_Shdr& shdr, const std::vector<uint8_t>& data);

} // namespace elf
