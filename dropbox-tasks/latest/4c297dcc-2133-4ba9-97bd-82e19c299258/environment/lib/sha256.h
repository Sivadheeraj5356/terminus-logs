#ifndef SHA256_H
#define SHA256_H

#include <stddef.h>

void sha256_hex(const unsigned char *data, size_t len, char out[65]);

#endif
