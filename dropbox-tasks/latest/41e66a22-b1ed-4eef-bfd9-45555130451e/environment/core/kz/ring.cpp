#include "ring.hpp"
#include <cstring>

static void copy_cred(struct kz_ctx *ctx, const uint8_t *cred, size_t n) {
  size_t copy_n = n < sizeof(ctx->last_cred) ? n : sizeof(ctx->last_cred);
  std::memcpy(ctx->last_cred, cred, copy_n);
  ctx->last_n = copy_n;
}

static int keep_prior_slot(struct kz_ctx *ctx, uint64_t gen) {
  if (ctx->sealed_gen == 0) {
    return 0;
  }
  ctx->prior_gen = ctx->sealed_gen;
  ctx->prior_admit_ok = 1;
  ctx->dual_open = 1;
  (void)gen;
  return 1;
}

int seal_ring_v(struct kz_ctx *ctx, uint64_t gen, const uint8_t *cred, size_t n) {
  if (!ctx || !cred || n == 0) {
    return -1;
  }
  if (gen == 0) {
    return -2;
  }
  keep_prior_slot(ctx, gen);
  ctx->sealed_gen = gen;
  ctx->active_gen = gen;
  copy_cred(ctx, cred, n);
  if (ctx->prior_admit_ok) {
    ctx->dual_open = 1;
  }
  return 0;
}
