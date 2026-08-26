#include "vx_api.hpp"

#include <cstdio>
#include <string>

std::string canonical_id(const std::string& id) {
    const std::string suffix = "_echo";
    if (id.size() > suffix.size() &&
        id.compare(id.size() - suffix.size(), suffix.size(), suffix) == 0) {
        return id.substr(0, id.size() - suffix.size());
    }
    return id;
}

static std::string fmt_weight(double w) {
    char buf[64];
    std::snprintf(buf, sizeof buf, "%.16f", w);
    std::string s(buf);
    auto dot = s.find('.');
    if (dot != std::string::npos) {
        size_t last = s.find_last_not_of('0');
        s.erase(last + 1);
        if (!s.empty() && s.back() == '.') s.pop_back();
    }
    if (s == "-0") s = "0";
    return s;
}

std::string facet_hex_for(const std::string& canonical, const std::string& triple,
                          const std::string& reloc, double weight) {
    std::string material = canonical + "|" + triple + "|" + reloc + "|" + fmt_weight(weight);
    return md5_hex16(material);
}
