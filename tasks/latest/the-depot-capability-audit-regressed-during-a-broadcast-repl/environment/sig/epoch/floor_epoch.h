#ifndef DEPOT_VAULT_FLOOR_EPOCH_H
#define DEPOT_VAULT_FLOOR_EPOCH_H

#include <stdint.h>

typedef struct {
    uint32_t floor_epoch;
} FloorState;

int floor_read_f(FloorState *out);

#endif
