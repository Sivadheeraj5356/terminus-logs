#include "field.h"

#include <stdio.h>
#include <stdlib.h>

double *field_alloc(int n) {
    double *u = (double *)calloc((size_t)n, sizeof(double));
    if (!u) {
        fprintf(stderr, "out of memory allocating field of length %d\n", n);
        exit(1);
    }
    return u;
}

double field_mass(const double *u_c, int N) {
    double s = 0.0;
    for (int i = 0; i < N; i++) {
        s += u_c[i];
    }
    return s / (double)N;
}

void field_minmax(const double *u_c, int N, double *lo, double *hi) {
    double mn = u_c[0], mx = u_c[0];
    for (int i = 1; i < N; i++) {
        if (u_c[i] < mn) {
            mn = u_c[i];
        }
        if (u_c[i] > mx) {
            mx = u_c[i];
        }
    }
    if (lo) {
        *lo = mn;
    }
    if (hi) {
        *hi = mx;
    }
}
