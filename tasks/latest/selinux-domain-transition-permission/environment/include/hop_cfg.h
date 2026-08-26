#ifndef HOP_CFG_H
#define HOP_CFG_H

#include <stdint.h>

#include "role_snap.h"

typedef struct HostCfg {
    char case_id[DCASE_ID];
    int entry_idx;
    char pivot[64];
    char pair_label[HC_NAME];
    RoleSnap src;
    RoleSnap alt;
    char line_text[HC_LINE];
    char gate_code;
    uint32_t cfg_mask;
    char role_sample[HC_NAME];
    uint32_t list_mask;
    uint32_t mask_bits;
    uint32_t bound_bits;
    uint32_t row_bits;
    uint32_t cap_ceil;
    char banner[HC_NAME];
    int lane_fd;
} HostCfg;

typedef struct {
    HostCfg items[DCASE_MAX];
    int count;
} HopSet;

int hops_load(const char *fixture_dir, HopSet *out);

#endif
