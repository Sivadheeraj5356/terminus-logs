#ifndef DEPOT_GATE_ADMIT_K_H
#define DEPOT_GATE_ADMIT_K_H

#include <stdint.h>

typedef enum {
    DEPOT_DECISION_ADMIT = 1,
    DEPOT_DECISION_DENY = 2,
} DepotDecision;

typedef struct {
    DepotDecision decision;
    const char *reason;
    int scope_ok;
    int epoch_ok;
} AdmitResult;

int gate_admit_k(const char *profile, int mac_ok, int revoke_hit, int scope_ok, int epoch_ok,
                 AdmitResult *out);

#endif
