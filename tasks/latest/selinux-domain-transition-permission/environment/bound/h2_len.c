#include "grant_buf.h"

#include <stdio.h>

size_t cap_byte_len(const CapSet *c)
{
    if (!c) {
        return 0;
    }
    return sizeof c->bits;
}
