#include "metrics/aggregate.hpp"
#include "metrics/goertzel.hpp"

#include <cstddef>
#include <vector>

namespace tone {

double aggregate_magnitude_sq(const std::vector<double>& windowed,
                              const std::vector<std::size_t>& bins) {
  double total = 0.0;
  for (std::size_t k : bins) {
    const GoertzelResult g = goertzel_bin(windowed, k);
    total += g.real * g.real + g.imag * g.imag;
  }
  return total;
}

}  // namespace tone
