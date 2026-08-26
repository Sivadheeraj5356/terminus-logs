#include "grant_buf.h"
#include "role_snap.h"

#include <stdio.h>

extern unsigned carry_peek(void);

int bind_cap(const RoleSnap *b, CapSet *out)
{
    if (!b || !out) {
        return -1;
    }
    out->bits = b->cap_bits | (carry_peek() & 0xffu);
    return 0;
}
