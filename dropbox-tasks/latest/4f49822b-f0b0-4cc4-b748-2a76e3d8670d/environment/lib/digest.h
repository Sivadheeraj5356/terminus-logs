#ifndef DEPOT_LIB_DIGEST_H
#define DEPOT_LIB_DIGEST_H

#include <stddef.h>

int depot_sha256_hex(const unsigned char *data, size_t len, char *out_hex, size_t out_cap);
int depot_hmac_sha256_hex(const unsigned char *key, size_t key_len, const unsigned char *msg,
                          size_t msg_len, char *out_hex, size_t out_cap);

#endif
