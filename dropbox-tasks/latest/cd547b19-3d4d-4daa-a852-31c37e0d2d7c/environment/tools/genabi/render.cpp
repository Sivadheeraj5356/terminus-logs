#include "render.hpp"

#include <cctype>
#include <cstdio>
#include <fstream>

namespace {

std::string macro_name(const std::string &field) {
    std::string upper;
    for (char c : field) {
        upper.push_back(static_cast<char>(std::toupper(static_cast<unsigned char>(c))));
    }
    return upper;
}

}  // namespace

bool render_header(const std::string &path, const LaneModel &model) {
    std::ofstream out(path);
    if (!out) {
        std::perror(path.c_str());
        return false;
    }
    out << "#ifndef SDK_ABI_SHAPE_HPP\n";
    out << "#define SDK_ABI_SHAPE_HPP\n\n";
    out << "#define SDK_LANE \"" << model.lane << "\"\n";
    out << "#define SDK_HAS_OBSERVABILITY " << (model.has_observability ? 1 : 0) << "\n";
    out << "#define SDK_HAS_DIAGNOSTICS " << (model.has_diagnostics ? 1 : 0) << "\n";
    out << "#define SDK_HAS_RECOVERY " << (model.has_recovery ? 1 : 0) << "\n";
    out << "#define SDK_FIELD_COUNT " << model.field_count << "\n";
    out << "#define SDK_RECORD_SIZE " << model.record_size << "\n";
    out << "#define SDK_RECORD_ALIGN " << model.record_align << "\n";
    out << "#define SDK_IDL_DIGEST \"" << model.digest << "\"\n\n";
    for (const Slot &slot : model.slots) {
        out << "#define SDK_OFF_" << macro_name(slot.name) << " " << slot.offset << "\n";
    }
    out << "\n#endif\n";
    return true;
}

bool render_layout(const std::string &path, const LaneModel &model) {
    std::ofstream out(path);
    if (!out) {
        std::perror(path.c_str());
        return false;
    }
    out << "{";
    out << "\"lane\":\"" << model.lane << "\"";
    out << ",\"record_size\":" << model.record_size;
    out << ",\"align\":" << model.record_align;
    out << ",\"field_count\":" << model.field_count;
    out << ",\"digest\":\"" << model.digest << "\"";
    out << ",\"fields\":[";
    for (std::size_t i = 0; i < model.slots.size(); ++i) {
        const Slot &slot = model.slots[i];
        if (i != 0) {
            out << ",";
        }
        out << "{\"slot\":" << slot.index;
        out << ",\"name\":\"" << slot.name << "\"";
        out << ",\"ctype\":\"" << ctype_of(slot.kind) << "\"";
        out << ",\"offset\":" << slot.offset;
        out << ",\"size\":" << slot.size << "}";
    }
    out << "]}\n";
    return true;
}
