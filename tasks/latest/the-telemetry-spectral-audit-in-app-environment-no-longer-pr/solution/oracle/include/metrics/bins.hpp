#pragma once

#include "metrics/types.hpp"

#include <cstddef>
#include <vector>

namespace tone {

std::vector<std::size_t> select_bins(std::size_t frame_len, double sample_rate_hz,
                                     const BandSpec& band);

}  // namespace tone
