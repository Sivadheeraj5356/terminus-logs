#include "vx_types.hpp"

#include <fstream>
#include <string>

static std::string seal_path(const std::string& root) { return root + "/meta/seal.bin"; }

std::string ReadSeal(const std::string& root) {
    std::ifstream in(seal_path(root));
    if (!in) return "";
    std::string body((std::istreambuf_iterator<char>(in)), std::istreambuf_iterator<char>());
    return body;
}

int RefreshSeal(const std::string& root, const std::string& id, const std::string& facet) {
    std::ofstream out(seal_path(root), std::ios::app);
    if (!out) return 1;
    out << "\"" << id << "\": \"" << facet << "\"\n";
    return 0;
}
