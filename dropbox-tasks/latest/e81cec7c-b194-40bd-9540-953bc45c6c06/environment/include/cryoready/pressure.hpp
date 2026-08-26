#pragma once

#include "cryoready/types.hpp"

namespace cryoready {

double pressure_psia(double pressure_psig);
bool pressure_ok(double pressure_psig, const ModelSpec& model);

}  // namespace cryoready
