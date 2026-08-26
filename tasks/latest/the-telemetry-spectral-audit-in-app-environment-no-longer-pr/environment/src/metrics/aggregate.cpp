#include "metrics/aggregate.hpp"
#include "metrics/goertzel.hpp"

#include <cmath>
#include <cstddef>
#include <vector>

namespace tone {

double aggregate_magnitude_sq(const std::vector<double>& windowed,
                              const std::vector<std::size_t>& bins) {
  double total = 0.0;
  for (std::size_t k : bins) {
    const GoertzelResult g = goertzel_bin(windowed, k);
    const double power = g.real * g.real + g.imag * g.imag;
    total += std::sqrt(power);
  }
  return total;
}

}  // namespace tone
