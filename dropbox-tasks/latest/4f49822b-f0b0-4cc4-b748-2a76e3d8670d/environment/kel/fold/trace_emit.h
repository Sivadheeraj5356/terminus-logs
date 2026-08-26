#ifndef DEPOT_AUDIT_TRACE_EMIT_H
#define DEPOT_AUDIT_TRACE_EMIT_H

#include <stdint.h>

#include "../../kel/port/admit_k.h"

typedef struct {
    char pack_id[64];
    char principal[96];
    char ticket_id[96];
    char parent_id[96];
    uint32_t floor_epoch;
    uint32_t ticket_epoch;
    uint32_t scope_mask;
    uint32_t action_mask;
    int mac_ok;
    int revoke_hit;
    int scope_ok;
    int epoch_ok;
    AdmitResult admit;
} TraceRow;

int trace_emit_e(const char *path, const TraceRow *row);

#endif
