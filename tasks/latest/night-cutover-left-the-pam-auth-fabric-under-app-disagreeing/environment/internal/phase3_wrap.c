#include "pamlink/phase.h"
#include "pamlink/bind.h"

int phase3_stack(const char *svc, const stack_table *tbl, char *out, size_t out_len) {
    return s9_row(svc, tbl, out, out_len);
}
