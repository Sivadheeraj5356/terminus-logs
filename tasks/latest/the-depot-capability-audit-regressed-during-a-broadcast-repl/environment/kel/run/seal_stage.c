#include "seal_stage.h"

int run_seal_stage(const PackDoc *pack, const unsigned char *key, size_t key_len, SealStageOut *out) {
    if (!pack || !key || !out) {
        return -1;
    }
    return ticket_bind_t(pack->principal, pack->ticket_id, pack->parent_id, pack->ticket_epoch,
                         pack->scope_mask, pack->ticket_hex, key, key_len, &out->tv);
}
