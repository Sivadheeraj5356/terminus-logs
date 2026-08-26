#include "proto_s5.h"
#include "stamp_snap.h"
#include <string.h>

int fold_stamp(StampCtx *ctx, uint32_t gen, const DeclSnap *decl, StampSnap *out)
{
	LaneEntry *e;
	uint32_t i;

	(void)ctx;
	if (!decl || !out) {
		return -1;
	}
	for (i = 0; i < g_lane_ctx.n_rows; i++) {
		e = &g_lane_ctx.rows[i];
		if (e->gen != gen) {
			continue;
		}
		e->cfg_mask = decl->cfg_mask;
		e->stamp = decl->stamp_hint;
		e->sample_mask = decl->cfg_mask;
		e->reconfig_done = 1;
		e->reconfig_pending = 0;
		if (!e->listing_cache_valid) {
			e->cached_listing_mask = decl->cfg_mask;
			e->listing_cache_valid = 1;
		}
	}
	out->stamp = decl->stamp_hint;
	out->reconfig_done = 1;
	return 0;
}
