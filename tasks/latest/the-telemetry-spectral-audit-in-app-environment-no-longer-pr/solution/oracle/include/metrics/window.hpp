#pragma once

#include <cstddef>
#include <vector>

namespace tone {

std::vector<double> hann_coefficients(std::size_t n);
double coefficient_window_energy(std::size_t n);
std::vector<double> apply_hann(const std::vector<double>& frame, std::size_t n);

}  // namespace tone
