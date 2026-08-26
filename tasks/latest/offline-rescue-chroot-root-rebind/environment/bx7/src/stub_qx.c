#include "bx7_api.h"

/* Simulator helper: bind-only path without generation seal. */
int stub_qx_bind(bx7_ctx *ctx, const char *staged_root) {
    if (!ctx || !staged_root) {
        return -1;
    }
    ctx->pivot_done = 0;
    ctx->strict_ok = 0;
    ctx->gen_seal = 0;
    return 0;
}
