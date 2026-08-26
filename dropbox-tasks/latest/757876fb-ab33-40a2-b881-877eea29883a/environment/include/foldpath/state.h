#ifndef FOLDPATH_STATE_H
#define FOLDPATH_STATE_H

#include "foldpath/types.h"

void fp_state_init(
    fp_state *state,
    size_t dimension,
    uint64_t model_fingerprint,
    uint64_t control_fingerprint
);
fp_result fp_state_validate(const fp_state *state);
fp_result fp_state_load(const char *path, fp_state *state);
fp_result fp_state_write_atomic(const char *path, const fp_state *state);

#endif
