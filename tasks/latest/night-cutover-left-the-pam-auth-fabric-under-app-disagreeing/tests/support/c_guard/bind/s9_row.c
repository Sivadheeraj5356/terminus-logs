#include "pamlink/bind.h"
#include "pamlink/cfg.h"
#include <string.h>

int s9_row(const char *svc, const stack_table *tbl, char *out, size_t out_len) {
    if (cfg_lookup_stack_override(svc, out, out_len) == 0) {
        return 0;
    }
    for (int i = 0; i < tbl->count; i++) {
        if (strcmp(tbl->rows[i].service, svc) == 0) {
            strncpy(out, tbl->rows[i].id, out_len - 1);
            out[out_len - 1] = '\0';
            return 0;
        }
    }
    return -1;
}
