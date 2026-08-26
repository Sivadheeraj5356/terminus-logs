#ifndef DEPOT_VAULT_CHAIN_LINK_H
#define DEPOT_VAULT_CHAIN_LINK_H

#include <stdint.h>

int chain_parent_scope(const char *ticket_id, const char *parent_id, uint32_t child_scope,
                       uint32_t *effective_scope);

#endif
