#include "quota.hpp"
#include <cstdio>

int main() {
  nx_ctx nx;
  nx_ctx_init(&nx, 7, 3, 2);
  if (fold_cap_m(&nx, 7, 2, 2) != 0) return 2;
  if (fold_cap_m(&nx, 7, 2, 2) != -4) return 3;
  if (fold_cap_m(&nx, 7, -1, 2) != 0) return 4;
  if (fold_cap_m(&nx, 7, 2, 2) != 0) return 5;
  if (fold_cap_m(&nx, 7, 1, 0) != -3) return 6;
  nx.held_after_reload = 1;
  if (fold_cap_m(&nx, 7, 0, 2) != 0) return 7;
  std::printf("occupancy=%d limit=%d\n", nx.occupancy, nx.limit);
  if (nx.occupancy != 3) return 8;
  if (nx.held_after_reload != 0) return 9;
  return 0;
}
