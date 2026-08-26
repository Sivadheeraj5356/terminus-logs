#pragma once

#include "cryoready/types.hpp"

namespace cryoready {

double fill_fraction(double level_liters, const ModelSpec& model);
bool fill_in_range(double fraction, const ModelSpec& model);

}  // namespace cryoready
