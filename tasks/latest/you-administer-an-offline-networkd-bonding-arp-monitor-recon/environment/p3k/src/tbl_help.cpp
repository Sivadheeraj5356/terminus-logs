#include "vx_api.hpp"

#include <string>
#include <vector>

std::string JoinNotes(const std::vector<std::string>& notes) {
    std::string out;
    for (size_t i = 0; i < notes.size(); ++i) {
        if (i) out += ",";
        out += notes[i];
    }
    return out;
}
