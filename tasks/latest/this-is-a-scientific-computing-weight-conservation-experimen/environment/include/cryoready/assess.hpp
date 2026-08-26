#pragma once

#include "cryoready/types.hpp"
#include <nlohmann/json.hpp>
#include <string>

namespace cryoready {

nlohmann::json build_readiness_report(
    const Facility& facility,
    const Catalog& catalog,
    const Maintenance& maint,
    const nlohmann::json& inventory_stage,
    const std::string& facility_path,
    const std::string& catalog_path,
    const std::string& maintenance_path);

}  // namespace cryoready
