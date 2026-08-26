#include "ring.hpp"
#include <cstdio>

int main() {
  kz_ctx kz;
  kz_ctx_init(&kz);
  const char *c1 = "a";
  const char *c2 = "b";
  const char *c3 = "c";
  seal_ring_v(&kz, 1, reinterpret_cast<const uint8_t *>(c1), 1);
  int d1 = (kz.dual_open && kz.prior_admit_ok) ? 1 : 0;
  seal_ring_v(&kz, 2, reinterpret_cast<const uint8_t *>(c2), 1);
  int d2 = (kz.dual_open && kz.prior_admit_ok) ? 1 : 0;
  seal_ring_v(&kz, 4, reinterpret_cast<const uint8_t *>(c3), 1);
  int d3 = (kz.dual_open && kz.prior_admit_ok) ? 1 : 0;
  std::printf("dual_seq=%d,%d,%d sealed=%llu\n", d1, d2, d3,
              static_cast<unsigned long long>(kz.sealed_gen));
  return (d1 == 0 && d2 == 0 && d3 == 0 && kz.sealed_gen == 4) ? 0 : 1;
}
