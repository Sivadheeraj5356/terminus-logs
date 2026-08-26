#include "../lane/ep/latch.hpp"

void ep_ctx_init(struct ep_ctx *ctx, uint64_t issued_at, uint64_t abs_span, uint64_t soft_span) {
  ctx->gen = 0;
  ctx->issued_at = issued_at;
  ctx->abs_span = abs_span;
  ctx->soft_span = soft_span;
  ctx->abs_deadline = issued_at + abs_span;
  ctx->last_activity = issued_at;
  ctx->soft_deadline = issued_at + soft_span;
  ctx->composed = 0;
  ctx->synced_gen = 0;
}
