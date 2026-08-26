#ifndef KEL_RUN_PORT_STAGE_H
#define KEL_RUN_PORT_STAGE_H

#include "../../kel/port/admit_k.h"
#include "bcast_stage.h"
#include "policy_stage.h"
#include "seal_stage.h"

typedef struct {
    AdmitResult admit;
} PortStageOut;

int run_port_stage(const char *profile, const SealStageOut *seal, const PolicyStageOut *policy,
                   const BcastStageOut *bcast, PortStageOut *out);

#endif
