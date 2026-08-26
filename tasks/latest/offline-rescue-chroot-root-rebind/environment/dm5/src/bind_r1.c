#include "dm5_api.h"

#include <string.h>

int stamp_r1(dm5_ctx *ctx, const backend_spec *spec, dev_epoch_t epoch, uint32_t gen) {
    size_t i;
    (void)epoch;
    (void)gen;
    if (!ctx || !spec) {
        return -1;
    }
    ctx->manifest_len = 0;
    ctx->manifest[0] = (uint8_t)spec->node_count;
    ctx->manifest_len = 1;
    for (i = 0; i < (size_t)spec->node_count && i < 8; i++) {
        size_t off = ctx->manifest_len;
        if (off + 4 > sizeof(ctx->manifest)) {
            return -2;
        }
        memcpy(ctx->manifest + off, &spec->majors[i], 2);
        memcpy(ctx->manifest + off + 2, &spec->minors[i], 2);
        ctx->manifest_len += 4;
    }
    return 0;
}
