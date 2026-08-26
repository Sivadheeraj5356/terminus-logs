#ifndef KEL_RUN_POLICY_STAGE_H
#define KEL_RUN_POLICY_STAGE_H

#include "../../lib/pack.h"

typedef struct {
    uint32_t effective_scope;
    int scope_ok;
    int epoch_ok;
    uint32_t floor_epoch;
} PolicyStageOut;

int run_policy_stage(const PackDoc *pack, PolicyStageOut *out);

#endif
