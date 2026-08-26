#include "pamlink/gate.h"
#include "pamlink/norm.h"
#include <string.h>

static int lookup_expiry(const char *actor, const acct_table *tbl) {
    char canon[PL_NAME_MAX];
    n4_norm(actor, canon, sizeof(canon));
    for (int i = 0; i < tbl->count; i++) {
        if (strcmp(tbl->rows[i].actor, canon) == 0) {
            return (int)tbl->rows[i].expiry;
        }
    }
    return 999999999;
}

int e1_gate(const char *actor, int64_t when, const acct_table *tbl) {
    return when >= lookup_expiry(actor, tbl);
}
