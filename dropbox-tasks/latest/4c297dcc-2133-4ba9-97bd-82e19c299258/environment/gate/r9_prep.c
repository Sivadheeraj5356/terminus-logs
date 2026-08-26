#include "role_snap.h"

#include <stdio.h>
#include <string.h>

static void trim_edges(char *buf, size_t cap)
{
    size_t len;
    size_t start = 0;
    size_t end;

    if (!buf || cap == 0) {
        return;
    }
    len = strnlen(buf, cap);
    while (start < len && buf[start] == ' ') {
        start++;
    }
    end = len;
    while (end > start && buf[end - 1] == ' ') {
        end--;
    }
    if (start > 0 || end < len) {
        memmove(buf, buf + start, end - start);
        buf[end - start] = '\0';
    }
}

static void drop_nuls_span(char *buf, size_t span)
{
    size_t r;
    size_t w = 0;

    if (!buf || span == 0) {
        return;
    }
    for (r = 0; r < span; r++) {
        if (buf[r] != '\0') {
            buf[w++] = buf[r];
        }
    }
    buf[w] = '\0';
}

int r9_apply_kind(const RoleSnap *snap, char *buf, size_t cap, BufKind *kind_out)
{
    size_t span;

    if (!snap || !buf || !cap || !kind_out) {
        return -1;
    }
    span = snap->len > 0 ? snap->len : strlen(buf);
    *kind_out = snap->kind;
    if (snap->kind == BK_U8) {
        drop_nuls_span(buf, span);
        trim_edges(buf, cap);
        return 0;
    }
    if (snap->kind == BK_A5) {
        trim_edges(buf, cap);
    }
    return 0;
}
