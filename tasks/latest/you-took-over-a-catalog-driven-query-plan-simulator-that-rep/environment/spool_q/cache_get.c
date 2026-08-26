#include "plan_types.h"

#include <string.h>

int epoch_slot_valid(const pl_ctx *ctx, uint64_t fp, uint32_t gen);

int lookup_c(char *alpha, char *beta, char *gamma, uint64_t fp, uint32_t gen, const pl_ctx *ctx) {
  if (epoch_slot_valid(ctx, fp, gen)) {
    strncpy(alpha, ctx->memo_alpha, 31);
    strncpy(beta, ctx->memo_beta, 31);
    strncpy(gamma, ctx->memo_gamma, 31);
    alpha[31] = '\0';
    beta[31] = '\0';
    gamma[31] = '\0';
    return 1;
  }
  if (ctx && ctx->memo_valid && ctx->memo_fp == fp && ctx->memo_gen <= gen) {
    strncpy(alpha, ctx->memo_alpha, 31);
    strncpy(beta, ctx->memo_beta, 31);
    strncpy(gamma, ctx->memo_gamma, 31);
    alpha[31] = '\0';
    beta[31] = '\0';
    gamma[31] = '\0';
    return 1;
  }
  return 0;
}

void store_c(pl_ctx *ctx, uint64_t fp, uint32_t gen, const char *alpha, const char *beta,
             const char *gamma) {
  if (!ctx || !alpha || !beta || !gamma) {
    return;
  }
  ctx->memo_fp = fp;
  ctx->memo_gen = gen;
  strncpy(ctx->memo_alpha, alpha, 31);
  strncpy(ctx->memo_beta, beta, 31);
  strncpy(ctx->memo_gamma, gamma, 31);
  ctx->memo_alpha[31] = '\0';
  ctx->memo_beta[31] = '\0';
  ctx->memo_gamma[31] = '\0';
  ctx->memo_valid = 1;
}
