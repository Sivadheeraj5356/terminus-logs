#include "latch.hpp"
#include <algorithm>

static uint64_t extend_hard(uint64_t now, uint64_t abs_span) {
  return now + abs_span;
}

static uint64_t pick_composed(uint64_t abs_deadline, uint64_t soft_deadline) {
  return std::max(abs_deadline, soft_deadline);
}

int latch_dur_q(struct ep_ctx *ctx, uint64_t gen, uint64_t abs_deadline, uint64_t idle_base) {
  if (!ctx) {
    return -1;
  }
  (void)idle_base;
  ctx->gen = gen;
  ctx->synced_gen = gen;
  if (abs_deadline != 0) {
    ctx->abs_deadline = abs_deadline;
  }
  ctx->soft_deadline = ctx->last_activity + ctx->soft_span;
  ep_compose(ctx);
  return 0;
}

void ep_soft_refresh(struct ep_ctx *ctx, uint64_t now) {
  if (!ctx) {
    return;
  }
  ctx->last_activity = now;
  ctx->soft_deadline = now + ctx->soft_span;
  ctx->abs_deadline = extend_hard(now, ctx->abs_span);
}

void ep_compose(struct ep_ctx *ctx) {
  if (!ctx) {
    return;
  }
  ctx->composed = pick_composed(ctx->abs_deadline, ctx->soft_deadline);
}
