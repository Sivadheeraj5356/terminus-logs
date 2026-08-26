#include "x.hpp"

#include <fstream>
#include <iterator>
#include <regex>
#include <stdexcept>
#include <string>

std::string z2_slurp(const std::string& path) {
    std::ifstream in(path);
    if (!in) {
        throw std::runtime_error("cannot open " + path);
    }
    return std::string(std::istreambuf_iterator<char>(in), std::istreambuf_iterator<char>());
}

GraphX z2_pull(const std::string& root) {
    GraphX g;
    std::string p1 = z2_slurp(root + "/inputs/p1.json");
    std::regex comp_re(R"rx(\{"name"\s*:\s*"([^"]+)"\s*,\s*"package"\s*:\s*"([^"]+)"\s*,\s*"hash"\s*:\s*"([^"]+)")rx");
    for (std::sregex_iterator it(p1.begin(), p1.end(), comp_re), end; it != end; ++it) {
        g.sig[(*it)[2].str()] = (*it)[3].str();
    }

    std::string p2 = z2_slurp(root + "/inputs/p2.json");
    std::regex node_re(R"rx(\{"package"\s*:\s*"([^"]+)"\s*,\s*"canonical"\s*:\s*"([^"]+)"\s*,\s*"component"\s*:\s*"([^"]+)")rx");
    for (std::sregex_iterator it(p2.begin(), p2.end(), node_re), end; it != end; ++it) {
        ItemX item;
        item.raw_pkg = (*it)[1].str();
        item.canon_pkg = (*it)[2].str();
        item.comp = (*it)[3].str();
        g.items.push_back(item);
    }
    return g;
}
