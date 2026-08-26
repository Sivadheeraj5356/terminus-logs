#include "pamlink/phase.h"
#include "pamlink/norm.h"

void phase4_canon(const char *raw, char *out, size_t out_len) {
    n4_norm(raw, out, out_len);
}
