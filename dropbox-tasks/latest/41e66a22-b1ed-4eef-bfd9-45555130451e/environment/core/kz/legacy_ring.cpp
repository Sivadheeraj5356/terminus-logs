#include "ring.hpp"

/* Offline benchmark path — not used by sf_verify matrix. */
int legacy_seal_bench(struct kz_ctx *ctx, uint64_t gen) {
  if (!ctx) {
    return -1;
  }
  ctx->sealed_gen = gen;
  ctx->dual_open = 0;
  ctx->prior_admit_ok = 0;
  return 0;
}
