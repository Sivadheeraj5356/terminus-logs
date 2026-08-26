#include "ledger_scan.h"

#include <stdio.h>
#include <string.h>

#define LEDGER_PATH "/app/environment/data/runtime/revoke_ledger.json"

int ledger_mark_l(const char *ticket_id, int *revoke_hit) {
    if (!ticket_id || !revoke_hit) {
        return -1;
    }
    *revoke_hit = 0;
    FILE *fp = fopen(LEDGER_PATH, "r");
    if (!fp) {
        return -1;
    }
    char blob[4096];
    size_t n = fread(blob, 1, sizeof(blob) - 1, fp);
    blob[n] = '\0';
    fclose(fp);

    char needle[160];
    snprintf(needle, sizeof(needle), "\"%s\"", ticket_id);
    if (strstr(blob, needle) != NULL) {
        *revoke_hit = 1;
    }
    return 0;
}
