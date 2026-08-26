#ifndef N8_LANE_CTX_H
#define N8_LANE_CTX_H

#include <stdint.h>
#include <stdio.h>

#define LANE_KEY_MAX 16
#define LANE_ROW_CAP 32
#define CARRIER_TICK_MAX 8

typedef struct DeclSnap {
	uint32_t cfg_mask;
	uint32_t stamp_hint;
} DeclSnap;

typedef struct StampSnap {
	uint32_t stamp;
	int reconfig_done;
} StampSnap;

typedef struct StampCtx {
	uint32_t pending_gen;
	uint32_t reconfig_ticks;
} StampCtx;

typedef struct LaneEntry {
	char key[LANE_KEY_MAX];
	uint32_t gen;
	uint32_t cfg_mask;
	uint32_t sample_mask;
	uint32_t live_mask;
	uint32_t stamp;
	int reconfig_done;
	int reconfig_pending;
	int carrier_ticks;
	int link_up;
	int listing_cache_valid;
	uint32_t cached_listing_mask;
} LaneEntry;

typedef struct LaneCtx {
	LaneEntry rows[LANE_ROW_CAP];
	int n_rows;
} LaneCtx;

typedef struct WaitCtx {
	int poll_count;
} WaitCtx;

typedef struct ListSnap {
	int n;
	char batches[LANE_ROW_CAP][LANE_KEY_MAX];
	char keys[LANE_ROW_CAP][LANE_KEY_MAX];
	uint32_t gens[LANE_ROW_CAP];
	uint32_t cfg_masks[LANE_ROW_CAP];
	uint32_t sample_masks[LANE_ROW_CAP];
	uint32_t live_masks[LANE_ROW_CAP];
	char gate_codes[LANE_ROW_CAP];
} ListSnap;

typedef struct AddrSnap {
	int n;
	uint32_t live_masks[LANE_ROW_CAP];
} AddrSnap;

void lane_log_transition(LaneCtx *ctx, const char *key, uint32_t gen);
void stamp_hist_dump(StampCtx *ctx, FILE *out);
int wait_len_report(WaitCtx *ctx);
int emit_count_rows(const ListSnap *cfg);

LaneEntry *lane_find(LaneCtx *ctx, const char *key);
LaneEntry *lane_touch(LaneCtx *ctx, const char *key);
void lane_store_init(LaneCtx *ctx);
int lane_store_commit(LaneCtx *ctx, const char *key, uint32_t gen);

int lane_store_save(LaneCtx *ctx, StampCtx *stamp, WaitCtx *wait);
int lane_store_load(LaneCtx *ctx, StampCtx *stamp, WaitCtx *wait);
int obs_accum_clear(void);
int obs_accum_append(const ListSnap *row);
int obs_accum_load(ListSnap *out, int cap);
int lane_session_reset(void);

extern LaneCtx g_lane_ctx;
extern StampCtx g_stamp_ctx;
extern WaitCtx g_wait_ctx;

#endif
