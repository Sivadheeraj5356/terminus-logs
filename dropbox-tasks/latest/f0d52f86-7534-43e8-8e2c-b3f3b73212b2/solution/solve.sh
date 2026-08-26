#!/bin/bash
set -euo pipefail

cd /app

# Install the oracle time integrator: sixth-order in space and time. The damped
# wave u_tt + 2 g u_t = c^2 u_xx is written as the first-order linear system
# u_t = w, w_t = c^2 D2(u) - 2 g w, with D2 the sixth-order 7-point periodic
# second-derivative stencil, and advanced with an eighth-term truncated matrix
# exponential (order eight in time) so that at a fixed Courant number the
# refinement slope is ~6. A merely fourth-order time integrator (e.g. classical
# RK4) would cap the joint rate at four and miss the band.
cat > src/scheme.c <<'CEOF'
#include "scheme.h"

#include <math.h>
#include <stdlib.h>
#include <string.h>

/* Sixth-order 7-point periodic second-derivative stencil
 *   D2(u)_i = ( u_{i-3}/90 - 3 u_{i-2}/20 + 3 u_{i-1}/2 - 49 u_i/18
 *               + 3 u_{i+1}/2 - 3 u_{i+2}/20 + u_{i+3}/90 ) / dx^2. */
static void d2_6(const double *u, double *out, int N, double invdx2) {
    for (int i = 0; i < N; i++) {
        int m3 = (i - 3 + N) % N, m2 = (i - 2 + N) % N, m1 = (i - 1 + N) % N;
        int p1 = (i + 1) % N, p2 = (i + 2) % N, p3 = (i + 3) % N;
        out[i] = ((1.0 / 90.0) * u[m3] - (3.0 / 20.0) * u[m2] +
                  (3.0 / 2.0) * u[m1] - (49.0 / 18.0) * u[i] +
                  (3.0 / 2.0) * u[p1] - (3.0 / 20.0) * u[p2] +
                  (1.0 / 90.0) * u[p3]) *
                 invdx2;
    }
}

/* Apply the linear operator L to (u, w): du = w, dw = c^2 D2(u) - 2 g w. */
static void applyL(const double *u, const double *w, double *du, double *dw,
                   int N, double c2, double g, double invdx2, double *tmp) {
    d2_6(u, tmp, N, invdx2);
    for (int i = 0; i < N; i++) {
        du[i] = w[i];
        dw[i] = c2 * tmp[i] - 2.0 * g * w[i];
    }
}

void scheme_advance(const Model *M, double *state, double t0, double t1) {
    double seg = t1 - t0;
    if (seg <= 0.0) {
        return;
    }
    int N = M->N;
    double dx = 1.0 / (double)N;
    double c = M->c, g = M->g;
    double c2 = c * c;
    double invdx2 = 1.0 / (dx * dx);

    double dt_nom = M->nu * dx / c;
    int nst = (int)ceil(seg / dt_nom - 1e-12);
    if (nst < 1) {
        nst = 1;
    }
    double dt = seg / (double)nst;

    double *u = state;
    double *w = state + N;

    double *su = (double *)malloc(sizeof(double) * (size_t)N);
    double *sw = (double *)malloc(sizeof(double) * (size_t)N);
    double *tu = (double *)malloc(sizeof(double) * (size_t)N);
    double *tw = (double *)malloc(sizeof(double) * (size_t)N);
    double *du = (double *)malloc(sizeof(double) * (size_t)N);
    double *dw = (double *)malloc(sizeof(double) * (size_t)N);
    double *tmp = (double *)malloc(sizeof(double) * (size_t)N);

    for (int step = 0; step < nst; step++) {
        /* Eighth-order truncated exponential: state <- sum_{j=0}^{8} (dt L)^j/j!
         * applied to (u, w). Exact in form for the linear operator and stable at
         * the Courant numbers used; both space and time are >= sixth order. */
        memcpy(su, u, sizeof(double) * (size_t)N);
        memcpy(sw, w, sizeof(double) * (size_t)N);
        memcpy(tu, u, sizeof(double) * (size_t)N);
        memcpy(tw, w, sizeof(double) * (size_t)N);
        for (int j = 1; j <= 8; j++) {
            applyL(tu, tw, du, dw, N, c2, g, invdx2, tmp);
            double f = dt / (double)j;
            for (int i = 0; i < N; i++) {
                tu[i] = f * du[i];
                tw[i] = f * dw[i];
                su[i] += tu[i];
                sw[i] += tw[i];
            }
        }
        memcpy(u, su, sizeof(double) * (size_t)N);
        memcpy(w, sw, sizeof(double) * (size_t)N);
    }

    free(su);
    free(sw);
    free(tu);
    free(tw);
    free(du);
    free(dw);
    free(tmp);
}
CEOF

make

mkdir -p /app/output
/app/solver /app/input/transport.json /app/output/field.csv

echo "oracle solve complete"
