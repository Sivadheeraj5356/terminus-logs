#include "quota.hpp"

int stub_fold_noop(struct nx_ctx *ctx, int delta) {
  if (!ctx) {
    return -1;
  }
  (void)delta;
  return 0;
}
