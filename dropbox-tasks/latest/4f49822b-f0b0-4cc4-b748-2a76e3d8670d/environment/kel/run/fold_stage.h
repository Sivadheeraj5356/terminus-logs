#ifndef KEL_RUN_FOLD_STAGE_H
#define KEL_RUN_FOLD_STAGE_H

#include "../../lib/pack.h"
#include "bcast_stage.h"
#include "policy_stage.h"
#include "port_stage.h"
#include "seal_stage.h"

int run_fold_stage(const char *path, const PackDoc *pack, const SealStageOut *seal,
                   const PolicyStageOut *policy, const BcastStageOut *bcast,
                   const PortStageOut *port);

#endif
