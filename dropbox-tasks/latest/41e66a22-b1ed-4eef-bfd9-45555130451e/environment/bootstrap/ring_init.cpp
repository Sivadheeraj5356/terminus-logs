#include "../core/kz/ring.hpp"
#include <cstring>

void kz_ctx_init(struct kz_ctx *ctx) {
  ctx->active_gen = 0;
  ctx->sealed_gen = 0;
  ctx->prior_gen = 0;
  ctx->dual_open = 0;
  ctx->prior_admit_ok = 0;
  ctx->last_n = 0;
  std::memset(ctx->last_cred, 0, sizeof(ctx->last_cred));
}
