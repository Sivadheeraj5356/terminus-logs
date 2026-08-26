#include "port_stage.h"

int run_port_stage(const char *profile, const SealStageOut *seal, const PolicyStageOut *policy,
                   const BcastStageOut *bcast, PortStageOut *out) {
    if (!seal || !policy || !bcast || !out) {
        return -1;
    }
    return gate_admit_k(profile, seal->tv.mac_ok, bcast->revoke_hit, policy->scope_ok, policy->epoch_ok,
                        &out->admit);
}
