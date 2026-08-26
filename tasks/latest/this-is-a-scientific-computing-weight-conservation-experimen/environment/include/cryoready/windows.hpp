#pragma once

#include "cryoready/types.hpp"
#include <string>

namespace cryoready {

bool in_maintenance(const Maintenance& maint, const std::string& vessel_id, long long epoch_unix);

}  // namespace cryoready
