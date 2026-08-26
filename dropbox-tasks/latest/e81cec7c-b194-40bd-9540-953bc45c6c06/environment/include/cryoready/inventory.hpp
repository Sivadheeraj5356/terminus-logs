#pragma once

#include "cryoready/types.hpp"
#include <nlohmann/json.hpp>
#include <string>

namespace cryoready {

nlohmann::json build_inventory_stage(
    const Facility& facility,
    const Catalog& catalog,
    const Maintenance& maint,
    const std::string& facility_path,
    const std::string& catalog_path,
    const std::string& maintenance_path);

std::string inventory_stage_path();
void write_inventory_stage(const nlohmann::json& stage);
nlohmann::json load_inventory_stage();

}  // namespace cryoready
