#ifndef GENABI_COMMON_HPP
#define GENABI_COMMON_HPP

#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

enum class Kind { U32, U64, PTR, CSTR };

struct Slot {
    std::string name;
    Kind kind;
    std::size_t offset = 0;
    std::size_t size = 0;
    int index = 0;
};

struct LaneModel {
    std::string lane;
    std::vector<Slot> slots;
    std::size_t record_size = 0;
    std::size_t record_align = 1;
    std::size_t field_count = 0;
    bool has_observability = false;
    bool has_diagnostics = false;
    bool has_recovery = false;
    std::string digest;
};

inline const char *ctype_of(Kind k) {
    switch (k) {
        case Kind::U32:
            return "uint32_t";
        case Kind::U64:
            return "uint64_t";
        case Kind::PTR:
            return "void*";
        case Kind::CSTR:
            return "const char*";
    }
    return "uint32_t";
}

inline std::size_t width_of(Kind k) {
    switch (k) {
        case Kind::U32:
            return 4;
        case Kind::U64:
        case Kind::PTR:
        case Kind::CSTR:
            return 8;
    }
    return 4;
}

#endif
