#include "lw3_api.h"

#include <stdio.h>

/* Dry-run helper: host-prefix cache without staged generation. */
int stub_lw_host(lw3_ctx *ctx, uint32_t epoch) {
    int n;
    if (!ctx) {
        return -1;
    }
    n = snprintf((char *)ctx->cache, sizeof(ctx->cache), "HOST=%u\n", epoch);
    if (n < 0 || (size_t)n >= sizeof(ctx->cache)) {
        return -2;
    }
    ctx->cache_len = (size_t)n;
    return 0;
}
