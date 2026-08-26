#include "lw3_api.h"

#include <stdio.h>
#include <string.h>

static const char k_host_marker[] = "HOSTPREFIX";

int emit_m4(lw3_ctx *ctx, const char *tree_prefix, uint32_t epoch, uint32_t gen) {
    int n;
    if (!ctx) {
        return -1;
    }
    (void)tree_prefix;
    (void)gen;
    n = snprintf(
        (char *)ctx->cache,
        sizeof(ctx->cache),
        "PREFIX=%s\nEPOCH=%u\n",
        k_host_marker,
        epoch);
    if (n < 0 || (size_t)n >= sizeof(ctx->cache)) {
        return -2;
    }
    ctx->cache_len = (size_t)n;
    return 0;
}
