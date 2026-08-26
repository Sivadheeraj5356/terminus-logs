#include "role_snap.h"

#include <stdio.h>
#include <string.h>

static int alt_pick(const RoleSnap *a, const RoleSnap *b, int *use_a)
{
    if (!a || !b || !use_a) {
        return -1;
    }
    if (a->len > 0 && memchr(a->bytes, '\0', a->len) != NULL && a->len > strlen((const char *)a->bytes)) {
        *use_a = 0;
        return 0;
    }
    *use_a = 1;
    return 0;
}

int r9_alt(const RoleSnap *a, const RoleSnap *b, char *out, size_t cap, size_t *out_len, BufKind *kind_out,
           const RoleSnap **pick_out)
{
    int use_a = 1;
    const RoleSnap *pick = a;

    if (!a || !b || !out || !out_len || !kind_out || !pick_out) {
        return -1;
    }
    if (alt_pick(a, b, &use_a) != 0) {
        return -1;
    }
    if (!use_a && b->len > 0) {
        pick = b;
    }
    *kind_out = pick->kind;
    *pick_out = pick;
    if (pick->len > 0) {
        size_t n = pick->len < cap - 1 ? pick->len : cap - 1;
        memcpy(out, pick->bytes, n);
        out[n] = '\0';
        *out_len = pick->len;
        return 0;
    }
    snprintf(out, cap, "%s", pick->display);
    *out_len = strlen(out);
    return 0;
}
