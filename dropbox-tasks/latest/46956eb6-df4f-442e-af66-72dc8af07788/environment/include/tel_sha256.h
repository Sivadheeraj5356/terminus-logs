#ifndef TEL_SHA256_H
#define TEL_SHA256_H

#include <stddef.h>

void tel_sha256_hex(const void *data, size_t len, char out_hex[65]);
void tel_sha256_raw(const void *data, size_t len, unsigned char out[32]);

#endif
