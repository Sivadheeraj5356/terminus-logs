#include "vx_types.hpp"

#include <string>

uint8_t BindOK(const std::string& seal, const std::string& id, const std::string& facet) {
    std::string needle = "\"" + id + "\": \"" + facet + "\"";
    return seal.find(needle) != std::string::npos ? 1 : 0;
}
