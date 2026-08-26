#include "next_fire.h"

#include <stdio.h>

void log_fire_audit(int64_t anchor, int64_t nxt) {
    fprintf(stderr, "fire-audit anchor=%lld nxt=%lld delta=%lld\n",
            (long long)anchor, (long long)nxt, (long long)(nxt - anchor));
}
