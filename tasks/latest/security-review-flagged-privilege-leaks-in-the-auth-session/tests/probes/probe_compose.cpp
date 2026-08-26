#include "latch.hpp"
#include <cstdio>

int main() {
  ep_ctx ep;
  ep_ctx_init(&ep, 1000, 100, 40);
  latch_dur_q(&ep, 1, 0, 0);
  ep_soft_refresh(&ep, 1020);
  ep_compose(&ep);
  ep_soft_refresh(&ep, 1040);
  ep_compose(&ep);
  ep_soft_refresh(&ep, 1090);
  ep_compose(&ep);
  ep_soft_refresh(&ep, 1600);
  ep_compose(&ep);
  std::printf("abs=%llu composed=%llu\n",
              static_cast<unsigned long long>(ep.abs_deadline),
              static_cast<unsigned long long>(ep.composed));
  if (ep.abs_deadline != 1100) return 2;
  if (ep.composed != 1100) return 3;
  return 0;
}
