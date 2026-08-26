#ifndef SHA256_LIB_H
#define SHA256_LIB_H

#include <stddef.h>

void sha256_hex(const unsigned char *data, size_t len, char *out_hex);
void sha256_hex_prefix(const unsigned char *data, size_t len, size_t n_hex, char *out_hex);

#endif
