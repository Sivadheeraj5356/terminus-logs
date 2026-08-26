#pragma once
#include <cstddef>
#include <cstdint>

struct kz_ctx {
  uint64_t active_gen;
  uint64_t sealed_gen;
  uint64_t prior_gen;
  int dual_open;
  int prior_admit_ok;
  uint8_t last_cred[64];
  size_t last_n;
};

int seal_ring_v(struct kz_ctx *ctx, uint64_t gen, const uint8_t *cred, size_t n);
void kz_ctx_init(struct kz_ctx *ctx);
