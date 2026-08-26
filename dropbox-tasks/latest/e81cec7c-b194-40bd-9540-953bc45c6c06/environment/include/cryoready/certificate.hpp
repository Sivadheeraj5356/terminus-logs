#pragma once

#include <nlohmann/json.hpp>

namespace cryoready {

nlohmann::json build_certificate(const nlohmann::json& report);

}  // namespace cryoready
