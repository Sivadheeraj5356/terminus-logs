#include "proto_l4.h"
#include <stdio.h>
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
	e->gen = gen;
	e->reconfig_pending = 1;
	e->reconfig_done = 0;
	return 0;
}
