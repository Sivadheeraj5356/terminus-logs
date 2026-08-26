#ifndef DEPOT_VAULT_TICKET_BIND_H
#define DEPOT_VAULT_TICKET_BIND_H

#include <stddef.h>
typedef struct {
    int mac_ok;
    char expect_hex[128];
} TicketVerify;

int ticket_bind_t(const char *principal, const char *ticket_id, const char *parent_id,
                  unsigned int epoch, unsigned int scope_mask, const char *ticket_hex,
                  const unsigned char *key, size_t key_len, TicketVerify *out);

#endif
