#ifndef KEL_RUN_BCAST_STAGE_H
#define KEL_RUN_BCAST_STAGE_H

#include "../../lib/pack.h"

typedef struct {
    int revoke_hit;
} BcastStageOut;

int run_bcast_stage(const PackDoc *pack, BcastStageOut *out);

#endif
