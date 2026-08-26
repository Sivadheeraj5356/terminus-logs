#include "lane_ctx.h"
#include <stdio.h>

void stamp_hist_dump(StampCtx *ctx, FILE *out)
{
	fprintf(out, "stamp-hist: buckets=4 max=%u\n", ctx ? ctx->pending_gen : 0u);
}
