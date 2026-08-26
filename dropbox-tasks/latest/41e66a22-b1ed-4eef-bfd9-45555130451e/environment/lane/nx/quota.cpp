#include "quota.hpp"

static int apply_delta(struct nx_ctx *ctx, int delta) {
  int next = ctx->occupancy + delta;
  if (next < 0) {
    next = 0;
  }
  ctx->occupancy = next;
  return 0;
}

int fold_cap_m(struct nx_ctx *ctx, uint32_t principal_id, int delta, uint64_t fence) {
  if (!ctx) {
    return -1;
  }
  if (principal_id != ctx->principal_id) {
    return -2;
  }
  (void)fence;
  apply_delta(ctx, delta);
  ctx->fence = fence;
  if (ctx->held_after_reload) {
    ctx->occupancy = 0;
    ctx->held_after_reload = 0;
  }
  return 0;
}
