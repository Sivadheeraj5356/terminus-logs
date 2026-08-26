#include "recover.h"

#include <stdlib.h>
#include <string.h>

int recover_events(const Catalog *catalog, const ObservationSet *observations, RecoveryResult *out) {
    (void)catalog;
    (void)observations;
    memset(out, 0, sizeof(*out));
    return 0;
}

void free_recovery_result(RecoveryResult *result) {
    free(result->events);
    memset(result, 0, sizeof(*result));
}
