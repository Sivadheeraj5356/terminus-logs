#include "bcast_stage.h"

#include "../../kel/bcast/ledger_scan.h"

int run_bcast_stage(const PackDoc *pack, BcastStageOut *out) {
    if (!pack || !out) {
        return -1;
    }
    return ledger_mark_l(pack->ticket_id, &out->revoke_hit);
}
