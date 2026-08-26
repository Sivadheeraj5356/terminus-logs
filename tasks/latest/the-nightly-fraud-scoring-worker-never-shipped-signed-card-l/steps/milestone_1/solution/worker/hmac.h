#ifndef HMAC_UTIL_H
#define HMAC_UTIL_H

#include <stddef.h>

int hmac_sha256_hex(
    const char *secret,
    const char *message,
    char *out_hex,
    size_t out_hex_size
);

#endif
