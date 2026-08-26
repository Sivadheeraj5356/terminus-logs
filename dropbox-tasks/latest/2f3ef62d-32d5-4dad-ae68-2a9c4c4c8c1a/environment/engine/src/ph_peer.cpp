#include "ph_iface.hpp"

#include <cstdint>
#include <string>
#include <utility>
#include <vector>

extern std::pair<uint8_t, std::vector<std::string>> FnR4(const std::string& tbl_path,
                                                         const std::vector<std::string>& seed_ids);

std::pair<uint8_t, std::vector<std::string>> expand_lanes(const std::string& staging_path,
                                                         const std::vector<std::string>& seed_ids) {
    return FnR4(staging_path, seed_ids);
}
