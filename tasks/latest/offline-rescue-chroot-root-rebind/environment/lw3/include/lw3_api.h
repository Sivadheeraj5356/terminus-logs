#ifndef LW3_API_H
#define LW3_API_H

#include <stddef.h>
#include <stdint.h>

typedef struct lw3_ctx {
    uint8_t cache[512];
    size_t cache_len;
} lw3_ctx;

int emit_m4(lw3_ctx *ctx, const char *tree_prefix, uint32_t epoch, uint32_t gen);

#endif
