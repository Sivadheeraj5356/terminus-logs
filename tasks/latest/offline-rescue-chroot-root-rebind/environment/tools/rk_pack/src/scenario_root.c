#include "scenario_root.h"

int scenario_root_rebind(bx7_ctx *ctx, const char *staged_root, cap_mode_t mode) {
    return render_q2(ctx, staged_root, mode);
}
