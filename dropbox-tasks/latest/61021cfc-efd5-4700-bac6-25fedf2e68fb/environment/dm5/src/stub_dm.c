#include "dm5_api.h"

#include <string.h>

/* Interim helper: static two-node list without backend parsing. */
int stub_dm_static(dm5_ctx *ctx) {
    uint16_t major;
    uint16_t minor;
    if (!ctx) {
        return -1;
    }
    ctx->manifest[0] = 2;
    ctx->manifest_len = 1;
    major = 1;
    minor = 5;
    memcpy(ctx->manifest + 1, &major, 2);
    memcpy(ctx->manifest + 3, &minor, 2);
    ctx->manifest_len = 5;
    major = 5;
    minor = 0;
    memcpy(ctx->manifest + 5, &major, 2);
    memcpy(ctx->manifest + 7, &minor, 2);
    ctx->manifest_len = 9;
    return 0;
}
