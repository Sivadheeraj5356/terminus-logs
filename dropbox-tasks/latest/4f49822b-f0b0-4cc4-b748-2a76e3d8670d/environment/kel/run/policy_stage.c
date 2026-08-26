#include "policy_stage.h"

#include "../../lib/scope.h"
#include "../../sig/epoch/floor_epoch.h"
#include "../../sig/range/chain_link.h"

extern int floor_epoch_ok(uint32_t ticket_epoch, uint32_t floor_epoch);

int run_policy_stage(const PackDoc *pack, PolicyStageOut *out) {
    if (!pack || !out) {
        return -1;
    }
    FloorState floor;
    if (floor_read_f(&floor) != 0) {
        return -1;
    }
    uint32_t effective_scope = pack->scope_mask;
    if (chain_parent_scope(pack->ticket_id, pack->parent_id, pack->scope_mask, &effective_scope) != 0) {
        return -1;
    }
    out->effective_scope = effective_scope;
    out->scope_ok = scope_covers(effective_scope, pack->action_mask);
    out->epoch_ok = floor_epoch_ok(pack->ticket_epoch, floor.floor_epoch);
    out->floor_epoch = floor.floor_epoch;
    return 0;
}
