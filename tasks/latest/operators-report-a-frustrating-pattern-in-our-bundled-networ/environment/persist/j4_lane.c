#include "lane_ctx.h"
#include "addr_snap.h"
#include <stdio.h>
#include <string.h>

#define LANE_STATE_PATH "/app/state/lane_ctx.dat"
#define OBS_ACCUM_PATH "/app/state/obs_accum.dat"

LaneCtx g_lane_ctx;
StampCtx g_stamp_ctx;
WaitCtx g_wait_ctx;

LaneEntry *lane_find(LaneCtx *ctx, const char *key)
{
	for (int i = 0; i < ctx->n_rows; i++) {
		if (strcmp(ctx->rows[i].key, key) == 0) {
			return &ctx->rows[i];
		}
	}
	return NULL;
}

LaneEntry *lane_touch(LaneCtx *ctx, const char *key)
{
	LaneEntry *e = lane_find(ctx, key);

	if (e) {
		return e;
	}
	if (ctx->n_rows >= LANE_ROW_CAP) {
		return NULL;
	}
	e = &ctx->rows[ctx->n_rows++];
	memset(e, 0, sizeof(*e));
	strncpy(e->key, key, LANE_KEY_MAX - 1);
	e->link_up = 1;
	return e;
}

void lane_store_init(LaneCtx *ctx)
{
	memset(ctx, 0, sizeof(*ctx));
}

int lane_store_commit(LaneCtx *ctx, const char *key, uint32_t gen)
{
	LaneEntry *e = lane_touch(ctx, key);

	if (!e) {
		return -1;
	}
	e->gen = gen;
	return 0;
}

int lane_store_save(LaneCtx *ctx, StampCtx *stamp, WaitCtx *wait)
{
	FILE *f = fopen(LANE_STATE_PATH, "wb");

	if (!f) {
		return -1;
	}
	fwrite(ctx, sizeof(*ctx), 1, f);
	fwrite(stamp, sizeof(*stamp), 1, f);
	fwrite(wait, sizeof(*wait), 1, f);
	fclose(f);
	return 0;
}

int lane_store_load(LaneCtx *ctx, StampCtx *stamp, WaitCtx *wait)
{
	FILE *f = fopen(LANE_STATE_PATH, "rb");

	if (!f) {
		lane_store_init(ctx);
		memset(stamp, 0, sizeof(*stamp));
		memset(wait, 0, sizeof(*wait));
		return 0;
	}
	fread(ctx, sizeof(*ctx), 1, f);
	fread(stamp, sizeof(*stamp), 1, f);
	fread(wait, sizeof(*wait), 1, f);
	fclose(f);
	return 0;
}

int obs_accum_clear(void)
{
	FILE *f = fopen(OBS_ACCUM_PATH, "wb");

	if (!f) {
		return -1;
	}
	fclose(f);
	return 0;
}

int obs_accum_append(const ListSnap *row)
{
	FILE *f = fopen(OBS_ACCUM_PATH, "ab");

	if (!f || !row || row->n != 1) {
		return -1;
	}
	fwrite(row, sizeof(*row), 1, f);
	fclose(f);
	return 0;
}

int obs_accum_load(ListSnap *out, int cap)
{
	FILE *f = fopen(OBS_ACCUM_PATH, "rb");
	ListSnap chunk;
	int n = 0;

	if (!f) {
		out->n = 0;
		return 0;
	}
	memset(out, 0, sizeof(*out));
	while (fread(&chunk, sizeof(chunk), 1, f) == 1 && n < cap) {
		if (chunk.n < 1) {
			continue;
		}
		memcpy(out->batches[n], chunk.batches[0], LANE_KEY_MAX);
		memcpy(out->keys[n], chunk.keys[0], LANE_KEY_MAX);
		out->gens[n] = chunk.gens[0];
		out->cfg_masks[n] = chunk.cfg_masks[0];
		out->sample_masks[n] = chunk.sample_masks[0];
		out->live_masks[n] = chunk.live_masks[0];
		out->gate_codes[n] = chunk.gate_codes[0];
		n++;
	}
	out->n = n;
	fclose(f);
	return n;
}

int lane_session_reset(void)
{
	obs_accum_clear();
	remove(LANE_STATE_PATH);
	lane_store_init(&g_lane_ctx);
	memset(&g_stamp_ctx, 0, sizeof(g_stamp_ctx));
	memset(&g_wait_ctx, 0, sizeof(g_wait_ctx));
	return 0;
}

uint32_t addr_mask_parse(const char *hex)
{
	unsigned long v = 0;

	if (!hex) {
		return 0;
	}
	if (hex[0] == '0' && (hex[1] == 'x' || hex[1] == 'X')) {
		sscanf(hex + 2, "%lx", &v);
	} else {
		sscanf(hex, "%lu", &v);
	}
	return (uint32_t)v;
}

void addr_mask_format(uint32_t mask, char *out, int out_len)
{
	snprintf(out, (size_t)out_len, "0x%08x", mask);
}

uint32_t lane_digest_fnv(const char *key, uint32_t gen, uint32_t cfg,
			 uint32_t sample, uint32_t live, char gate)
{
	uint32_t h = 2166136261u;
	const char *p = key;

	while (p && *p) {
		h ^= (uint8_t)*p++;
		h *= 16777619u;
	}
	h ^= gen;
	h *= 16777619u;
	h ^= cfg;
	h *= 16777619u;
	h ^= sample;
	h *= 16777619u;
	h ^= live;
	h *= 16777619u;
	h ^= (uint32_t)gate;
	h *= 16777619u;
	return h;
}

uint32_t bundle_digest_fnv(const char *payload)
{
	uint32_t h = 2166136261u;

	for (const unsigned char *p = (const unsigned char *)payload; p && *p; p++) {
		h ^= *p;
		h *= 16777619u;
	}
	return h;
}
