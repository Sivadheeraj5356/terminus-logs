#include "plan_types.h"

#include <string.h>

void pl_reset(pl_ctx *ctx) {
  memset(ctx, 0, sizeof(*ctx));
}

static void pick_join(double sel_left, double sel_right, uint32_t rows_left, uint32_t rows_right,
                      char *alpha, char *beta) {
  double cost_nl = sel_left * (double)rows_right;
  double cost_hj = (double)rows_left + (double)rows_right;
  if (cost_nl < cost_hj) {
    strcpy(alpha, "nest_loop");
    strcpy(beta, "build_left");
  } else {
    strcpy(alpha, "hash_join");
    strcpy(beta, "build_right");
  }
}

void drive_plan(pl_ctx *ctx, uint64_t fp, int partial_req, char *alpha, char *beta, char *gamma,
                uint32_t *stats_gen_out) {
  uint32_t gen = ctx->live_gen;
  if (ctx->snap_valid && ctx->resume_pending) {
    merge_a(&gen, ctx->snap_gen, ctx->live_gen);
  }
  if (stats_gen_out) {
    *stats_gen_out = gen;
  }
  if (lookup_c(alpha, beta, gamma, fp, gen, ctx)) {
    return;
  }
  const pl_table *t0 = &ctx->tables[0];
  const pl_table *t1 = &ctx->tables[1];
  const pl_table *snap0 = ctx->snap_valid ? &ctx->snap_tables[0] : NULL;
  int use_snap = ctx->snap_valid && ctx->resume_pending;
  double sel0 = est_b(t0, snap0, use_snap, 1);
  double sel1 = est_b(t1, snap0, use_snap, 2);
  pick_join(sel0, sel1, t0->rows, t1->rows, alpha, beta);
  uint32_t probe_vis = ctx->resume_pending ? ctx->snap_vis_gen : ctx->vis_gen;
  if (probe_d(probe_vis, ctx->vis_gen, (uint64_t)t0->rows, partial_req)) {
    strcpy(gamma, "partial_scan");
  } else {
    strcpy(gamma, "seq_scan");
  }
  store_c(ctx, fp, gen, alpha, beta, gamma);
}
