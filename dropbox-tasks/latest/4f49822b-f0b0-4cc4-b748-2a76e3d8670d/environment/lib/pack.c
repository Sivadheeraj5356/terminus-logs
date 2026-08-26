#include "pack.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int json_string(const char *blob, const char *key, char *out, size_t cap) {
    char pattern[128];
    snprintf(pattern, sizeof(pattern), "\"%s\"", key);
    const char *p = strstr(blob, pattern);
    if (!p) {
        return -1;
    }
    p = strchr(p, ':');
    if (!p) {
        return -1;
    }
    p++;
    while (*p == ' ' || *p == '\t') {
        p++;
    }
    if (*p != '"') {
        return -1;
    }
    p++;
    const char *end = strchr(p, '"');
    if (!end) {
        return -1;
    }
    size_t n = (size_t)(end - p);
    if (n >= cap) {
        n = cap - 1;
    }
    memcpy(out, p, n);
    out[n] = '\0';
    return 0;
}

static int json_uint(const char *blob, const char *key, uint32_t *out) {
    char pattern[128];
    snprintf(pattern, sizeof(pattern), "\"%s\"", key);
    const char *p = strstr(blob, pattern);
    if (!p) {
        return -1;
    }
    p = strchr(p, ':');
    if (!p) {
        return -1;
    }
    return sscanf(p + 1, "%u", out) == 1 ? 0 : -1;
}

int pack_load_json(const char *path, PackDoc *out) {
    if (!path || !out) {
        return -1;
    }
    FILE *fp = fopen(path, "r");
    if (!fp) {
        return -1;
    }
    char blob[4096];
    size_t n = fread(blob, 1, sizeof(blob) - 1, fp);
    blob[n] = '\0';
    fclose(fp);

    memset(out, 0, sizeof(*out));
    if (json_string(blob, "pack_id", out->pack_id, sizeof(out->pack_id)) != 0) {
        return -1;
    }
    if (json_string(blob, "principal", out->principal, sizeof(out->principal)) != 0) {
        return -1;
    }
    if (json_string(blob, "ticket_id", out->ticket_id, sizeof(out->ticket_id)) != 0) {
        return -1;
    }
    if (json_string(blob, "parent_id", out->parent_id, sizeof(out->parent_id)) != 0) {
        out->parent_id[0] = '\0';
    }
    if (json_uint(blob, "ticket_epoch", &out->ticket_epoch) != 0) {
        return -1;
    }
    if (json_uint(blob, "scope_mask", &out->scope_mask) != 0) {
        return -1;
    }
    if (json_uint(blob, "action_mask", &out->action_mask) != 0) {
        return -1;
    }
    if (json_string(blob, "profile", out->profile, sizeof(out->profile)) != 0) {
        strncpy(out->profile, "standard", sizeof(out->profile) - 1);
    }
    if (json_string(blob, "ticket_hex", out->ticket_hex, sizeof(out->ticket_hex)) != 0) {
        return -1;
    }
    return 0;
}
