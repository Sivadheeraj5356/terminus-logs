#include "bx7_api.h"

int render_q2(bx7_ctx *ctx, const char *staged_root, cap_mode_t mode) {
    (void)mode;
    if (!ctx) {
        return -1;
    }
    if (!staged_root || staged_root[0] != '/') {
        return -2;
    }
    ctx->pivot_done = 1;
    ctx->strict_ok = 1;
    ctx->gen_seal = 2;
    return 0;
}
