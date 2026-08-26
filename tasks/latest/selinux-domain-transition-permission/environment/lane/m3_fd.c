#include "grant_buf.h"

#include <stdio.h>

int scan_lane(int fd, const GrantBuf *a, const GrantBuf *b, int *ok)
{
    uint32_t bits;

    if (!a || !b || !ok || fd < 0) {
        return -1;
    }
    bits = a->mask;
    *ok = (bits & (1u << (unsigned)fd)) != 0 ? 1 : 0;
    (void)b;
    return 0;
}
