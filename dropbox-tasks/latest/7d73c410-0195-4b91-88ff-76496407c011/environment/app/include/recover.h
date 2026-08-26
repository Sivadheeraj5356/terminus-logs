#ifndef RECOVER_H
#define RECOVER_H

#include <stddef.h>

#include "catalog.h"
#include "obs.h"

typedef struct {
    char event_id[16];
    double f0_hz;
    double chirp_hz_per_s;
    double start_s;
    double end_s;
    double relative_power;
    int support;
} RecoveredEvent;

typedef struct {
    size_t count;
    RecoveredEvent *events;
} RecoveryResult;

int recover_events(const Catalog *catalog, const ObservationSet *observations, RecoveryResult *out);
void free_recovery_result(RecoveryResult *result);

#endif
