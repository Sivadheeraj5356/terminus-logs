#include "pamlink/norm.h"
#include "pamlink/cfg.h"
#include <ctype.h>
#include <string.h>

void n4_norm(const char *raw, char *out, size_t out_len) {
    if (out_len == 0) {
        return;
    }

    char mode[32] = "lower";
    cfg_load_realm_mode(mode, sizeof(mode));

    const char *at = strrchr(raw, '@');
    if (!at || strcmp(mode, "preserve") == 0) {
        strncpy(out, raw, out_len - 1);
        out[out_len - 1] = '\0';
        return;
    }

    size_t left_len = (size_t)(at - raw);
    if (left_len >= out_len) {
        left_len = out_len - 1;
    }
    memcpy(out, raw, left_len);
    out[left_len] = '@';
    size_t pos = left_len + 1;
    for (const char *p = at + 1; *p && pos + 1 < out_len; p++, pos++) {
        out[pos] = (char)tolower((unsigned char)*p);
    }
    out[pos] = '\0';
}
