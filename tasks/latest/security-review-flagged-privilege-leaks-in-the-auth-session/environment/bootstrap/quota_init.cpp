#include "../lane/nx/quota.hpp"

void nx_ctx_init(struct nx_ctx *ctx, uint32_t principal_id, int limit, uint64_t expected_fence) {
  ctx->principal_id = principal_id;
  ctx->occupancy = 0;
  ctx->limit = limit;
  ctx->fence = 0;
  ctx->expected_fence = expected_fence;
  ctx->held_after_reload = 0;
}
