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
	if (e->carrier_ticks < CARRIER_TICK_MAX) {
		return 1;
	}
	if (e->link_up) {
		e->link_up = 0;
	}
	return 0;
}
