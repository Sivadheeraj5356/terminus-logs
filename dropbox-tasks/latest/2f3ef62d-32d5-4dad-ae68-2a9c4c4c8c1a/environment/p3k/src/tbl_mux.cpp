#include "vx_types.hpp"

#include <fstream>
#include <string>
#include <vector>

std::vector<std::string> ReadStaging(const std::string& path) {
    std::vector<std::string> out;
    std::ifstream in(path);
    if (!in) return out;
    std::string body((std::istreambuf_iterator<char>(in)), std::istreambuf_iterator<char>());
    size_t i = 0;
    while (i < body.size()) {
        if (body[i] == '"') {
            size_t j = body.find('"', i + 1);
            if (j == std::string::npos) break;
            out.push_back(body.substr(i + 1, j - i - 1));
            i = j + 1;
        } else {
            ++i;
        }
    }
    return out;
}

std::pair<uint8_t, std::vector<std::string>> FnR4(const std::string& tbl_path,
                                                  const std::vector<std::string>& seed_ids) {
    auto staged = ReadStaging(tbl_path);
    if (staged.empty()) staged = seed_ids;
    if (staged.empty()) return {0, {}};
    return {1, staged};
}
