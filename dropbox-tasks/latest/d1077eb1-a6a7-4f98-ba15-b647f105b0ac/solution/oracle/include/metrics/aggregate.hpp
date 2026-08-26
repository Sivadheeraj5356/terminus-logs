#pragma once

#include <cstddef>
#include <vector>

namespace tone {

double aggregate_magnitude_sq(const std::vector<double>& windowed,
                              const std::vector<std::size_t>& bins);

}  // namespace tone
