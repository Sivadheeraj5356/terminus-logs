#include "foldpath/state.h"

#include <string.h>

/*
 * Deliberate task scaffold.
 *
 * The public types and function boundaries are provided so foldmodel-check and
 * the starter library build cleanly. The continuation command must complete
 * checkpoint validation, integrity protection, serialization, loading, and
 * atomic persistence (or replace this module with an equivalent design).
 */

void fp_state_init(
    fp_state *state,
    size_t dimension,
    uint64_t model_fingerprint,
    uint64_t control_fingerprint
)
{
    if (state == NULL) {
        return;
    }
    memset(state, 0, sizeof(*state));
    state->dimension = dimension;
    state->model_fingerprint = model_fingerprint;
    state->control_fingerprint = control_fingerprint;
    state->status = FP_STATUS_PARTIAL;
}

fp_result fp_state_validate(const fp_state *state)
{
    (void)state;
    return FP_INVALID;
}

fp_result fp_state_load(const char *path, fp_state *state)
{
    (void)path;
    (void)state;
    return FP_INVALID;
}

fp_result fp_state_write_atomic(const char *path, const fp_state *state)
{
    (void)path;
    (void)state;
    return FP_INVALID;
}
