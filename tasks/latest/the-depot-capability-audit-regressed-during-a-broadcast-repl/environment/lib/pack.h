#ifndef DEPOT_LIB_PACK_H
#define DEPOT_LIB_PACK_H

#include <stdint.h>

#define PACK_ID_MAX 64
#define PRINCIPAL_MAX 96
#define TICKET_ID_MAX 96
#define PARENT_ID_MAX 96
#define PROFILE_MAX 32
#define HEX_MAX 128

typedef struct {
    char pack_id[PACK_ID_MAX];
    char principal[PRINCIPAL_MAX];
    char ticket_id[TICKET_ID_MAX];
    char parent_id[PARENT_ID_MAX];
    uint32_t ticket_epoch;
    uint32_t scope_mask;
    uint32_t action_mask;
    char profile[PROFILE_MAX];
    char ticket_hex[HEX_MAX];
} PackDoc;

int pack_load_json(const char *path, PackDoc *out);

#endif
