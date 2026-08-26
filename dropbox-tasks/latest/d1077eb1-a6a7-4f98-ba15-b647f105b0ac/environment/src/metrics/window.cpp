#include "metrics/window.hpp"

#include <cmath>
#include <cstddef>
#include <vector>

namespace tone {

std::vector<double> hann_coefficients(std::size_t n) {
  std::vector<double> coeffs(n);
  if (n == 0) {
    return coeffs;
  }
  if (n == 1) {
    coeffs[0] = 1.0;
    return coeffs;
  }
  for (std::size_t i = 0; i < n; ++i) {
    coeffs[i] = 0.5 * (1.0 - std::cos(2.0 * M_PI * static_cast<double>(i) / static_cast<double>(n)));
  }
  return coeffs;
}

double coefficient_window_energy(std::size_t n) {
  const std::vector<double> coeffs = hann_coefficients(n);
  double sum = 0.0;
  for (double c : coeffs) {
    sum += c;
  }
  return sum;
}

std::vector<double> apply_hann(const std::vector<double>& frame, std::size_t n) {
  const std::vector<double> coeffs = hann_coefficients(n);
  std::vector<double> out(n);
  for (std::size_t i = 0; i < n; ++i) {
    out[i] = frame[i] * coeffs[i];
  }
  return out;
}

}  // namespace tone
