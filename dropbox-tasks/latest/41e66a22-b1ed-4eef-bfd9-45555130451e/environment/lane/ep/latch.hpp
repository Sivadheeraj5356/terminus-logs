#pragma once
#include <cstdint>

struct ep_ctx {
  uint64_t gen;
  uint64_t issued_at;
  uint64_t abs_deadline;
  uint64_t soft_deadline;
  uint64_t soft_span;
  uint64_t abs_span;
  uint64_t last_activity;
  uint64_t composed;
  uint64_t synced_gen;
};

void ep_ctx_init(struct ep_ctx *ctx, uint64_t issued_at, uint64_t abs_span, uint64_t soft_span);
int latch_dur_q(struct ep_ctx *ctx, uint64_t gen, uint64_t abs_deadline, uint64_t idle_base);
void ep_soft_refresh(struct ep_ctx *ctx, uint64_t now);
void ep_compose(struct ep_ctx *ctx);
