#include "gamma_repairer.hpp"
#include "elf_helper.hpp"
#include <iostream>
#include <vector>
#include <cstring>

namespace reloc {

bool repair_gamma_section(const std::string& path, const Elf64_Shdr& shdr) {
    std::vector<uint8_t> data;
    if (!elf::read_section_data(path, shdr, data)) {
        return false;
    }

    if (data.size() < 8) {
        return true; // Too small to be encoded, treat as noop
    }

    uint32_t magic = 0;
    uint32_t num_entries = 0;
    std::memcpy(&magic, data.data(), 4);
    std::memcpy(&num_entries, data.data() + 4, 4);

    if (magic != 0x474D524C) {
        // Section is not encoded or already repaired
        return true;
    }

    std::vector<Elf64_Rela> unpacked(num_entries);
    const uint8_t* packed_ptr = data.data() + 8;

    for (uint32_t i = 0; i < num_entries; ++i) {
        if (static_cast<size_t>((packed_ptr - data.data()) + 16) > data.size()) {
            std::cerr << "Error: Packed stream out of bounds" << std::endl;
            return false;
        }

        uint32_t r_offset_lo = 0;
        uint32_t sym_idx = 0;
        int32_t addend = 0;
        uint8_t r_type = 0;

        std::memcpy(&r_offset_lo, packed_ptr, 4);
        std::memcpy(&sym_idx, packed_ptr + 4, 4);
        std::memcpy(&addend, packed_ptr + 8, 4);
        std::memcpy(&r_type, packed_ptr + 12, 1);

        // r_offset is stored as low 32 bits; zero-extend to uint64
        uint64_t r_offset = static_cast<uint64_t>(r_offset_lo);
        uint64_t r_info = (static_cast<uint64_t>(sym_idx) << 32) | r_type;
        int64_t r_addend = static_cast<int64_t>(addend);

        unpacked[i].r_offset = r_offset;
        unpacked[i].r_info = r_info;
        unpacked[i].r_addend = r_addend;

        packed_ptr += 16;
    }

    // Convert to byte vector and extend with zeroes to match original section size
    std::vector<uint8_t> new_data(shdr.sh_size, 0);
    size_t bytes_to_copy = num_entries * sizeof(Elf64_Rela);
    if (bytes_to_copy > shdr.sh_size) {
        std::cerr << "Error: Unpacked relocations exceed section size" << std::endl;
        return false;
    }

    std::memcpy(new_data.data(), unpacked.data(), bytes_to_copy);
    return elf::write_section_data(path, shdr, new_data);
}

} // namespace reloc
