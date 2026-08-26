#ifndef PLAN_TYPES_H
#define PLAN_TYPES_H

#include <stddef.h>
#include <stdint.h>

#define PL_MAX_TABLE 4
#define PL_MAX_BUCK 8
#define PL_MAX_STEP 64

typedef struct {
  uint32_t rows;
  uint32_t distinct;
  uint32_t buckets;
  uint32_t bounds[PL_MAX_BUCK];
  uint32_t stats_gen;
} pl_table;

typedef struct {
  pl_table tables[PL_MAX_TABLE];
  int table_n;
  uint32_t live_gen;
  uint32_t vis_gen;
  uint32_t snap_vis_gen;
  int snap_valid;
  pl_table snap_tables[PL_MAX_TABLE];
  uint32_t snap_bounds[PL_MAX_TABLE][PL_MAX_BUCK];
  uint32_t snap_gen;
  int resume_pending;
  char memo_alpha[32];
  char memo_beta[32];
  char memo_gamma[32];
  uint32_t memo_gen;
  uint64_t memo_fp;
  int memo_valid;
} pl_ctx;

typedef struct {
  char scenario_id[64];
  char mode[16];
  char step_alpha_id[32];
  char step_beta_id[32];
  char step_gamma_id[32];
  uint32_t stats_gen;
  int stats_ok;
  int pair_ok;
  char plan_digest[17];
  char finish_reason[8];
} pl_row;

void pl_reset(pl_ctx *ctx);
int merge_a(uint32_t *out_gen, uint32_t persisted, uint32_t live);
double est_b(const pl_table *live, const pl_table *snap, int use_snap_bounds, int pred_bucket);
int lookup_c(char *alpha, char *beta, char *gamma, uint64_t fp, uint32_t gen, const pl_ctx *ctx);
void store_c(pl_ctx *ctx, uint64_t fp, uint32_t gen, const char *alpha, const char *beta,
             const char *gamma);
int probe_d(uint32_t vis_gen, uint32_t live_vis, uint64_t row_est, int partial_req);
uint64_t fold_fp(const char *tag);
void drive_plan(pl_ctx *ctx, uint64_t fp, int partial_req, char *alpha, char *beta, char *gamma,
                uint32_t *stats_gen_out);

#endif
