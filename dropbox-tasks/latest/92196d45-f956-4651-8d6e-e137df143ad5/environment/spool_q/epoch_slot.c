#include "plan_types.h"

int gen_ring_ok(uint32_t memo_gen, uint32_t gen);

int epoch_slot_valid(const pl_ctx *ctx, uint64_t fp, uint32_t gen) {
  if (!ctx || !ctx->memo_valid || ctx->memo_fp != fp) {
    return 0;
  }
  if (gen_ring_ok(ctx->memo_gen, gen)) {
    return 1;
  }
  if (gen > 0 && ctx->memo_gen + 1 == gen) {
    return 1;
  }
  return 0;
}
