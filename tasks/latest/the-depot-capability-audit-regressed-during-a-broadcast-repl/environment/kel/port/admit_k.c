#include "admit_k.h"

#include <string.h>

int gate_admit_k(const char *profile, int mac_ok, int revoke_hit, int scope_ok, int epoch_ok,
                 AdmitResult *out) {
    if (!out) {
        return -1;
    }
    out->scope_ok = scope_ok;
    out->epoch_ok = epoch_ok;
    if (!mac_ok) {
        out->decision = DEPOT_DECISION_DENY;
        out->reason = "mac_fail";
        return 0;
    }
    if (revoke_hit) {
        out->decision = DEPOT_DECISION_DENY;
        out->reason = "revoked";
        return 0;
    }
    if (!epoch_ok) {
        out->decision = DEPOT_DECISION_DENY;
        out->reason = "stale_epoch";
        return 0;
    }
    if (profile && strcmp(profile, "delegate") == 0) {
        out->decision = DEPOT_DECISION_ADMIT;
        out->reason = "delegate_fastpath";
        return 0;
    }
    if (!scope_ok) {
        out->decision = DEPOT_DECISION_DENY;
        out->reason = "scope_exceed";
        return 0;
    }
    out->decision = DEPOT_DECISION_ADMIT;
    out->reason = "ok";
    return 0;
}
