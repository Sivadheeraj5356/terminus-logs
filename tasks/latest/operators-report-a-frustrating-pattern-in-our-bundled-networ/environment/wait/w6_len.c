#include "lane_ctx.h"

int wait_len_report(WaitCtx *ctx)
{
	if (!ctx) {
		return 0;
	}
	ctx->poll_count++;
	return ctx->poll_count;
}
