#pragma once

#include "cryoready/types.hpp"
#include <string>

namespace cryoready {

Facility load_facility(const std::string& path);
Catalog load_catalog(const std::string& path);
Maintenance load_maintenance(const std::string& path);
const ModelSpec* find_model(const Catalog& catalog, const std::string& model_id);

}  // namespace cryoready
