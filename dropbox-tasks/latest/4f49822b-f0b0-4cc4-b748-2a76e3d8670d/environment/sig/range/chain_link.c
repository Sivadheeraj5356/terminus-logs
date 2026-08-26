#include "chain_link.h"

#include <stdio.h>
#include <string.h>

#define CATALOG_PATH "/app/environment/data/tickets/catalog.json"

static int catalog_scope(const char *ticket_id, uint32_t *scope_out) {
    FILE *fp = fopen(CATALOG_PATH, "r");
    if (!fp) {
        return -1;
    }
    char blob[8192];
    size_t n = fread(blob, 1, sizeof(blob) - 1, fp);
    blob[n] = '\0';
    fclose(fp);

    char pattern[160];
    snprintf(pattern, sizeof(pattern), "\"ticket_id\": \"%s\"", ticket_id);
    const char *p = strstr(blob, pattern);
    if (!p) {
        return -1;
    }
    const char *scope_key = strstr(p, "\"scope_mask\"");
    if (!scope_key) {
        return -1;
    }
    return sscanf(strchr(scope_key, ':') + 1, "%u", scope_out) == 1 ? 0 : -1;
}

int chain_parent_scope(const char *ticket_id, const char *parent_id, uint32_t child_scope,
                       uint32_t *effective_scope) {
    (void)ticket_id;
    if (!effective_scope) {
        return -1;
    }
    if (!parent_id || parent_id[0] == '\0') {
        *effective_scope = child_scope;
        return 0;
    }
    uint32_t parent_scope = 0;
    if (catalog_scope(parent_id, &parent_scope) != 0) {
        return -1;
    }
    *effective_scope = child_scope | parent_scope;
    return 0;
}
