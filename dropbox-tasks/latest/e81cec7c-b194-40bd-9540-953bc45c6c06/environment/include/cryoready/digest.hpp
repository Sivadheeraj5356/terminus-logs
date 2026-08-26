#pragma once

#include <nlohmann/json.hpp>
#include <string>

namespace cryoready {

std::string sha256_file(const std::string& path);
std::string sha256_bytes(const std::string& data);
std::string canonical_json_compact(const nlohmann::json& doc);

}  // namespace cryoready
