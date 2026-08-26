#pragma once

#include <cstddef>
#include <vector>

namespace tone {

struct GoertzelResult {
  double real{};
  double imag{};
};

GoertzelResult goertzel_bin(const std::vector<double>& windowed, std::size_t k);

}  // namespace tone
