#include "proto_l4.h"

int h2_admit_lane(LaneCtx *lc, const char *key, uint32_t gen)
{
	return admit_lane(lc, key, gen);
}
