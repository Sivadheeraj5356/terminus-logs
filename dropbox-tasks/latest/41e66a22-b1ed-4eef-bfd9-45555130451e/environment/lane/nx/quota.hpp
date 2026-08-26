#pragma once
#include <cstdint>

struct nx_ctx {
  uint32_t principal_id;
  int occupancy;
  int limit;
  uint64_t fence;
  uint64_t expected_fence;
  int held_after_reload;
};

void nx_ctx_init(struct nx_ctx *ctx, uint32_t principal_id, int limit, uint64_t expected_fence);
int fold_cap_m(struct nx_ctx *ctx, uint32_t principal_id, int delta, uint64_t fence);
