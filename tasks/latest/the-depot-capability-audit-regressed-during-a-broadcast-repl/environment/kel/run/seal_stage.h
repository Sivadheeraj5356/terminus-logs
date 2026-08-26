#ifndef KEL_RUN_SEAL_STAGE_H
#define KEL_RUN_SEAL_STAGE_H

#include "../../lib/pack.h"
#include "../../sig/seal/ticket_bind.h"

typedef struct {
    TicketVerify tv;
} SealStageOut;

int run_seal_stage(const PackDoc *pack, const unsigned char *key, size_t key_len, SealStageOut *out);

#endif
