#include "metrics/goertzel.hpp"

#include <cmath>
#include <cstddef>
#include <vector>

namespace tone {

GoertzelResult run_goertzel(const std::vector<double>& x, std::size_t k) {
  const std::size_t n = x.size();
  if (n == 0) {
    return {};
  }
  const double omega = 2.0 * M_PI * static_cast<double>(k) / static_cast<double>(n);
  const double coeff = 2.0 * std::cos(omega);
  double s0 = 0.0;
  double s1 = 0.0;
  double s2 = 0.0;
  for (double sample : x) {
    s0 = sample + coeff * s1 - s2;
    s2 = s1;
    s1 = s0;
  }
  const double real = s1 - s2 * std::cos(omega);
  const double imag = s2 * std::sin(omega);
  return {real, imag};
}

GoertzelResult goertzel_bin(const std::vector<double>& windowed, std::size_t k) {
  return run_goertzel(windowed, k);
}

}  // namespace tone
