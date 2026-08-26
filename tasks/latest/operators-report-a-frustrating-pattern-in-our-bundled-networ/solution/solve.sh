#!/usr/bin/env bash
set -euo pipefail

cat > /app/environment/l4/l4_admit.c <<'ENDFIX'
#include "proto_l4.h"
#include <string.h>

int admit_lane(LaneCtx *ctx, const char *key, uint32_t gen)
{
	LaneEntry *e;

	if (!ctx || !key) {
		return -1;
	}
	e = lane_touch(ctx, key);
	if (!e) {
		return -2;
	}
	if (gen < e->gen) {
		return -3;
	}
	if (gen > e->gen) {
		e->listing_cache_valid = 0;
		e->cached_listing_mask = 0;
	}
	e->gen = gen;
	e->reconfig_pending = 1;
	e->reconfig_done = 0;
	return 0;
}
ENDFIX

cat > /app/environment/stamp/s5_fold.c <<'ENDFIX'
#include "proto_s5.h"
#include <string.h>

int fold_stamp(StampCtx *ctx, uint32_t gen, const DeclSnap *decl, StampSnap *out)
{
	LaneEntry *e;
	uint32_t i;

	if (!decl || !out) {
		return -1;
	}
	for (i = 0; i < g_lane_ctx.n_rows; i++) {
		e = &g_lane_ctx.rows[i];
		if (e->gen != gen || !e->reconfig_pending) {
			continue;
		}
		e->cfg_mask = decl->cfg_mask;
		if (ctx->reconfig_ticks > 0) {
			e->stamp = decl->stamp_hint;
			e->sample_mask = decl->cfg_mask;
			e->live_mask = decl->cfg_mask;
			e->reconfig_done = 1;
			e->reconfig_pending = 0;
			e->cached_listing_mask = decl->cfg_mask;
			e->listing_cache_valid = 1;
		} else {
			if (e->listing_cache_valid) {
				e->sample_mask = e->cached_listing_mask;
			}
			e->reconfig_done = 0;
			e->reconfig_pending = 1;
		}
	}
	out->stamp = decl->stamp_hint;
	out->reconfig_done = ctx->reconfig_ticks > 0;
	return 0;
}
ENDFIX

cat > /app/environment/wait/w6_hold.c <<'ENDFIX'
#include "proto_w6.h"
#include <string.h>

int gate_wait(WaitCtx *ctx, const char *key, uint32_t gen)
{
	LaneEntry *e;

	(void)ctx;
	e = lane_find(&g_lane_ctx, key);
	if (!e || e->gen != gen) {
		return -1;
	}
	e->carrier_ticks++;
	if (e->carrier_ticks < 1) {
		return 1;
	}
	if (e->link_up) {
		e->link_up = 0;
	}
	e->live_mask = 0;
	e->cfg_mask = 0;
	e->sample_mask = 0;
	return 0;
}
ENDFIX

cat > /app/environment/m7/m7_snap.c <<'ENDFIX'
#include "proto_m7.h"
#include "addr_snap.h"
#include <stdio.h>
#include <string.h>

int emit_snap(const ListSnap *cfg, const AddrSnap *live, FILE *out)
{
	char line[256];
	char payload[4096];
	int pos = 0;

	if (!cfg || !live || !out) {
		return -1;
	}
	payload[0] = '\0';
	fprintf(out, "{\n  \"profile\": \"concurrency_ordering\",\n  \"rows\": [\n");
	for (int i = 0; i < cfg->n; i++) {
		uint32_t cfgm = cfg->cfg_masks[i];
		uint32_t sample = cfg->sample_masks[i];
		uint32_t live_mask = cfg->live_masks[i];
		char gate = cfg->gate_codes[i];

		if (i < live->n) {
			LaneEntry *e = lane_find(&g_lane_ctx, cfg->keys[i]);
			if (e && e->gen == cfg->gens[i]) {
				live_mask = live->live_masks[i];
			}
		}
		if (gate == 'D') {
			cfgm = 0;
			sample = 0;
			live_mask = 0;
		}
		uint32_t dig = lane_digest_fnv(cfg->keys[i], cfg->gens[i], cfgm, sample, live_mask, gate);
		snprintf(line, sizeof(line),
			 "    {\"batch\": \"%s\", \"key\": \"%s\", \"gen\": %u, \"gate_code\": \"%c\", "
			 "\"cfg_mask\": %u, \"sample_mask\": %u, \"live_mask\": %u, "
			 "\"lane_digest\": \"0x%08x\"}%s\n",
			 cfg->batches[i], cfg->keys[i], cfg->gens[i], gate, cfgm, sample, live_mask, dig,
			 (i + 1 < cfg->n) ? "," : "");
		fprintf(out, "%s", line);
		pos += snprintf(payload + pos, sizeof(payload) - (size_t)pos,
				"%s:%u:%u:%u:%u:%c;", cfg->batches[i], cfg->gens[i], cfgm, sample,
				live_mask, gate);
	}
	uint32_t bundle = bundle_digest_fnv(payload);
	fprintf(out, "  ],\n  \"lane_digest\": \"0x%08x\"\n}\n", bundle);
	return 0;
}
ENDFIX

make -C /app/environment -j2
mkdir -p /app/output /app/state
/app/tools/n2_driver --reset --batch w00
/app/tools/n2_driver --batch w01 --fixture r_row_a
/app/tools/n2_driver --batch w02 --fixture r_row_b
/app/tools/n2_driver --batch w03 --fixture r_row_c
/app/tools/n2_driver --batch w04 --fixture r_row_a2
/app/tools/n2_driver --batch w05 --fixture r_row_b2
/app/tools/n2_driver --batch w06 --fixture r_row_c2
/app/tools/n2_driver --batch w07 --fixture r_row_a3
/app/tools/n2_driver --batch w08 --fixture r_row_b3
/app/tools/w8_emit
