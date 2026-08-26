#include "csvout.h"

#include <stddef.h>

FILE *csv_open(const char *path) {
    return fopen(path, "wb");
}

void csv_header(FILE *o) {
    fprintf(o, "t,x,u,v\n");
}

void csv_write_snapshot(FILE *o, double ts, const double *x, const double *state,
                        int N) {
    for (int i = 0; i < N; i++) {
        fprintf(o, "%.16e,%.16e,%.16e,%.16e\n", ts, x[i], state[i],
                state[(size_t)N + i]);
    }
}
