#include "metrics/bins.hpp"
#include "metrics/types.hpp"

#include <cmath>
#include <cstddef>
#include <vector>

namespace tone {

std::vector<std::size_t> select_bins(std::size_t frame_len, double sample_rate_hz,
                                     const BandSpec& band) {
  std::vector<std::size_t> bins;
  if (frame_len == 0 || sample_rate_hz <= 0.0) {
    return bins;
  }
  const std::size_t max_k = frame_len / 2;
  for (std::size_t k = 0; k <= max_k; ++k) {
    const double freq = static_cast<double>(k) * sample_rate_hz / static_cast<double>(frame_len);
    if (freq + 1e-12 >= band.low_hz && freq <= band.high_hz + 1e-12) {
      bins.push_back(k);
    }
  }
  return bins;
}

}  // namespace tone
