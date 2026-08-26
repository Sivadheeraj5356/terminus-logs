#include "grant_buf.h"
#include "role_snap.h"

#include <stdio.h>

int pick_mask(const RoleSnap *a, const RoleSnap *b, GrantBuf *out)
{
    if (!a || !b || !out) {
        return -1;
    }
    out->mask = a->cap_bits ? a->cap_bits : b->cap_bits;
    return 0;
}
