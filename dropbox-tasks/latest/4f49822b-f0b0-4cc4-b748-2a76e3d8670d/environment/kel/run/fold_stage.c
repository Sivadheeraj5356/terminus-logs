#include "fold_stage.h"

#include "../../kel/fold/trace_emit.h"

#include <string.h>

int run_fold_stage(const char *path, const PackDoc *pack, const SealStageOut *seal,
                   const PolicyStageOut *policy, const BcastStageOut *bcast,
                   const PortStageOut *port) {
    if (!path || !pack || !seal || !policy || !bcast || !port) {
        return -1;
    }
    TraceRow row;
    memset(&row, 0, sizeof(row));
    strncpy(row.pack_id, pack->pack_id, sizeof(row.pack_id) - 1);
    strncpy(row.principal, pack->principal, sizeof(row.principal) - 1);
    strncpy(row.ticket_id, pack->ticket_id, sizeof(row.ticket_id) - 1);
    strncpy(row.parent_id, pack->parent_id, sizeof(row.parent_id) - 1);
    row.floor_epoch = policy->floor_epoch;
    row.ticket_epoch = pack->ticket_epoch;
    row.scope_mask = pack->scope_mask;
    row.action_mask = pack->action_mask;
    row.mac_ok = seal->tv.mac_ok;
    row.revoke_hit = bcast->revoke_hit;
    row.scope_ok = policy->scope_ok;
    row.epoch_ok = policy->epoch_ok;
    row.admit = port->admit;
    return trace_emit_e(path, &row);
}
