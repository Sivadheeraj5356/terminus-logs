#include "ph_iface.hpp"

#include <cstdint>
#include <string>

extern uint64_t FnM7(uint64_t gen, bool flush);

std::string reloc_note_after_flush(uint64_t start_gen) {
    uint64_t gen = FnM7(start_gen, true);
    return "g" + std::to_string(gen);
}
