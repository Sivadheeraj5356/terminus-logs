#include <cstddef>
#include <cstdint>

std::size_t stash_encode_tail(const double* vals, std::size_t n) {
  std::size_t span = 0;
  double prev = 0.0;
  for (std::size_t i = 0; i < n; ++i) {
    double dx = vals[i] - prev;
    if (dx < 0.0) {
      dx = -dx;
    }
    span ^= static_cast<std::size_t>(dx * 4096.0) + i * 9176u;
    prev = vals[i];
  }
  return span % 1337u;
}
