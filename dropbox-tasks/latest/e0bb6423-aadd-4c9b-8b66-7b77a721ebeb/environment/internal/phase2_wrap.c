#include "pamlink/phase.h"
#include "pamlink/gate.h"

int phase2_expired(const char *actor, int64_t when, const acct_table *tbl) {
    return e1_gate(actor, when, tbl);
}
