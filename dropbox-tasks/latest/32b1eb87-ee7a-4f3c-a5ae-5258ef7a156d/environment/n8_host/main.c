#include "harness.h"
#include "addr_snap.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int parse_fixture_line(const char *line, char *key, uint32_t *gen,
			      uint32_t *cfg, int *carrier_down, int *delay)
{
	char cfg_hex[32] = {0};
	char carrier[16] = {0};

	if (!line || line[0] == '#' || line[0] == '\n') {
		return 0;
	}
	if (sscanf(line, "key=%15s gen=%u cfg=%31s carrier=%15s reconfig_delay=%d",
		   key, gen, cfg_hex, carrier, delay) < 4) {
		return 0;
	}
	*cfg = addr_mask_parse(cfg_hex);
	*carrier_down = (strcmp(carrier, "down") == 0);
	return 1;
}

static uint32_t probe_live(LaneEntry *e)
{
	if (!e->link_up) {
		return 0;
	}
	if (e->reconfig_done && e->live_mask != e->cfg_mask) {
		return e->live_mask;
	}
	if (e->reconfig_done) {
		return e->cfg_mask;
	}
	return e->live_mask ? e->live_mask : e->sample_mask;
}

static char classify_row(LaneEntry *e)
{
	uint32_t probe = probe_live(e);

	if (e->cfg_mask != e->sample_mask || e->sample_mask != probe) {
		return 'D';
	}
	return 'A';
}

static void push_obs(const char *batch, LaneEntry *e)
{
	ListSnap one;

	memset(&one, 0, sizeof(one));
	one.n = 1;
	strncpy(one.batches[0], batch, LANE_KEY_MAX - 1);
	strncpy(one.keys[0], e->key, LANE_KEY_MAX - 1);
	one.gens[0] = e->gen;
	one.cfg_masks[0] = e->cfg_mask;
	one.sample_masks[0] = e->sample_mask;
	one.live_masks[0] = probe_live(e);
	one.gate_codes[0] = classify_row(e);
	obs_accum_append(&one);
}

static int run_fixture(const char *path, const char *batch)
{
	FILE *f = fopen(path, "r");
	char line[256];
	char key[LANE_KEY_MAX];
	uint32_t gen = 0;
	uint32_t cfg = 0;
	int carrier_down = 0;
	int delay = 0;

	if (!f) {
		return -1;
	}
	while (fgets(line, sizeof(line), f)) {
		if (!parse_fixture_line(line, key, &gen, &cfg, &carrier_down, &delay)) {
			continue;
		}
		LaneEntry *e;
		DeclSnap decl;
		StampSnap snap;

		memset(&decl, 0, sizeof(decl));
		memset(&snap, 0, sizeof(snap));
		decl.cfg_mask = cfg;
		decl.stamp_hint = gen * 17u + 3u;
		g_stamp_ctx.reconfig_ticks = 0;
		if (h2_admit_lane(&g_lane_ctx, key, gen) != 0) {
			fclose(f);
			return -2;
		}
		for (int tick = 0; tick < delay; tick++) {
			g_stamp_ctx.reconfig_ticks++;
		}
		if (h5_fold_decl(&g_stamp_ctx, gen, &decl, &snap) != 0) {
			fclose(f);
			return -2;
		}
		e = lane_find(&g_lane_ctx, key);
		if (!e) {
			fclose(f);
			return -3;
		}
		if (e->live_mask == 0 && e->cfg_mask != 0 && gen == 1) {
			e->live_mask = e->cfg_mask;
		}
		if (carrier_down) {
			while (h3_poll_carrier(&g_wait_ctx, key, gen) > 0) {
				/* poll carrier window */
			}
		} else {
			e->link_up = 1;
		}
		if (!e->link_up && carrier_down) {
			e->live_mask = 0;
		}
		lane_store_commit(&g_lane_ctx, key, gen);
		push_obs(batch, e);
	}
	fclose(f);
	return 0;
}

static int run_baseline_batch(const char *batch)
{
	LaneEntry *e;

	e = lane_touch(&g_lane_ctx, "k0");
	if (!e) {
		return -1;
	}
	e->gen = 1;
	e->cfg_mask = 0x0a000001u;
	e->sample_mask = 0x0a000001u;
	e->live_mask = 0x0a000001u;
	e->reconfig_done = 1;
	e->link_up = 1;
	e->stamp = 20;
	push_obs(batch, e);

	e = lane_touch(&g_lane_ctx, "k1");
	if (!e) {
		return -1;
	}
	e->gen = 1;
	e->cfg_mask = 0x0a000002u;
	e->sample_mask = 0x0a000002u;
	e->live_mask = 0x0a000002u;
	e->reconfig_done = 1;
	e->link_up = 1;
	e->stamp = 21;
	push_obs(batch, e);
	return 0;
}

static int run_batch(const char *batch, const char *fixture)
{
	char path[512];
	int rc;

	if (fixture && fixture[0]) {
		snprintf(path, sizeof(path), "/app/environment/n8_replays/%s/h8_fixture/blob.frag",
			 fixture);
		rc = run_fixture(path, batch);
	} else {
		rc = run_baseline_batch(batch);
	}
	lane_store_save(&g_lane_ctx, &g_stamp_ctx, &g_wait_ctx);
	return rc;
}

static int cmd_replay(int argc, char **argv)
{
	const char *batch = NULL;
	const char *fixture = NULL;

	for (int i = 1; i < argc; i++) {
		if (strcmp(argv[i], "--batch") == 0 && i + 1 < argc) {
			batch = argv[++i];
		} else if (strcmp(argv[i], "--fixture") == 0 && i + 1 < argc) {
			fixture = argv[++i];
		} else if (strcmp(argv[i], "--reset") == 0) {
			lane_session_reset();
		}
	}
	if (!batch) {
		fprintf(stderr, "usage: n8_host replay --batch NAME [--fixture DIR] [--reset]\n");
		return 2;
	}
	lane_store_load(&g_lane_ctx, &g_stamp_ctx, &g_wait_ctx);
	return run_batch(batch, fixture);
}

static int cmd_emit(int argc, char **argv)
{
	ListSnap obs;
	AddrSnap live;
	FILE *out;
	const char *path = "/app/output/n8_observations.json";

	(void)argc;
	(void)argv;
	lane_store_load(&g_lane_ctx, &g_stamp_ctx, &g_wait_ctx);
	memset(&obs, 0, sizeof(obs));
	obs_accum_load(&obs, LANE_ROW_CAP);
	live.n = obs.n;
	for (int i = 0; i < obs.n; i++) {
		LaneEntry *e = lane_find(&g_lane_ctx, obs.keys[i]);
		live.live_masks[i] = e ? probe_live(e) : obs.live_masks[i];
	}
	out = fopen(path, "w");
	if (!out) {
		return 1;
	}
	if (h4_write_obs(&obs, &live, out) != 0) {
		fclose(out);
		return 1;
	}
	fclose(out);
	return 0;
}

int main(int argc, char **argv)
{
	if (argc < 2) {
		fprintf(stderr, "usage: n8_host replay|emit\n");
		return 2;
	}
	if (strcmp(argv[1], "replay") == 0) {
		return cmd_replay(argc - 1, argv + 1);
	}
	if (strcmp(argv[1], "emit") == 0) {
		return cmd_emit(argc - 1, argv + 1);
	}
	fprintf(stderr, "unknown command: %s\n", argv[1]);
	return 2;
}
