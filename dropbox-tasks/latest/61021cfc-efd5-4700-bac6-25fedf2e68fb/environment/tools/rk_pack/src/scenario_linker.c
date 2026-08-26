#include "scenario_linker.h"

int scenario_linker_cache(lw3_ctx *ctx, const char *tree_prefix, uint32_t epoch, uint32_t gen) {
    return emit_m4(ctx, tree_prefix, epoch, gen);
}
