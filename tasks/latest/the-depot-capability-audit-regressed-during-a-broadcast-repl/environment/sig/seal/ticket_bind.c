#include "ticket_bind.h"

#include "../../lib/digest.h"

#include <stdio.h>
#include <string.h>
#include <strings.h>

int ticket_bind_t(const char *principal, const char *ticket_id, const char *parent_id,
                  unsigned int epoch, unsigned int scope_mask, const char *ticket_hex,
                  const unsigned char *key, size_t key_len, TicketVerify *out) {
    (void)parent_id;
    if (!principal || !ticket_id || !ticket_hex || !key || !out) {
        return -1;
    }
    char bind_msg[512];
    snprintf(bind_msg, sizeof(bind_msg), "%s|%s|%u|%u", principal, ticket_id, epoch, scope_mask);
    if (depot_hmac_sha256_hex(key, key_len, (const unsigned char *)bind_msg, strlen(bind_msg),
                              out->expect_hex, sizeof(out->expect_hex)) != 0) {
        return -1;
    }
    out->mac_ok = (strcasecmp(out->expect_hex, ticket_hex) == 0) ? 1 : 0;
    return 0;
}
