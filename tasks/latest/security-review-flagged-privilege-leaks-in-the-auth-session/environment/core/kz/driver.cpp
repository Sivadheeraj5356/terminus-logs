#include "ring.hpp"

int kz_probe_prior(const struct kz_ctx *ctx, uint64_t prior) {
  if (!ctx) {
    return -1;
  }
  if (ctx->prior_gen == prior && ctx->prior_admit_ok) {
    return 1;
  }
  return 0;
}
