#ifndef DM5_API_H
#define DM5_API_H

#include <stddef.h>
#include <stdint.h>

typedef uint32_t dev_epoch_t;

typedef struct backend_spec {
    char name[32];
    int node_count;
    uint16_t majors[8];
    uint16_t minors[8];
} backend_spec;

typedef struct dm5_ctx {
    uint8_t manifest[256];
    size_t manifest_len;
} dm5_ctx;

int stamp_r1(dm5_ctx *ctx, const backend_spec *spec, dev_epoch_t epoch, uint32_t gen);

#endif
