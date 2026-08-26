#ifndef BX7_API_H
#define BX7_API_H

#include <stdint.h>

typedef enum {
    CAP_STRICT = 0,
    CAP_RELAXED = 1
} cap_mode_t;

typedef struct bx7_ctx {
    int strict_ok;
    int pivot_done;
    uint32_t gen_seal;
} bx7_ctx;

int render_q2(bx7_ctx *ctx, const char *staged_root, cap_mode_t mode);

#endif
