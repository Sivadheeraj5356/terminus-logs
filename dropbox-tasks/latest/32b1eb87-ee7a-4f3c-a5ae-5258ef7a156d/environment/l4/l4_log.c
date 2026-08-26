#include "lane_ctx.h"
#include <stdio.h>

void lane_log_transition(LaneCtx *ctx, const char *key, uint32_t gen)
{
	LaneEntry *e = lane_find(ctx, key);

	if (!e) {
		fprintf(stderr, "lane-log: missing %s gen=%u\n", key, gen);
		return;
	}
	fprintf(stderr, "lane-log: %s gen=%u stamp=%u sample=0x%08x\n",
		key, gen, e->stamp, e->sample_mask);
}
