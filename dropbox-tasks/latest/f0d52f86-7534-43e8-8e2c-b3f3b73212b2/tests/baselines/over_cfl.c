#include "harness.h"

/* Over-CFL: the correct fourth-order space stencil and RK4 time integration, but
 * the step is sized from an oversized fixed Courant number (ignoring the input
 * nu), well above the stability limit of the explicit scheme. The high modes
 * amplify each step and the field grows without bound, so the finiteness and
 * energy checks reject it. */
#define OVER_NU 3.5

static void rhs(const double *u, const double *w, double *du, double *dw, int N,
                double c2, double g, double inv12dx2) {
    double *lap = malloc(sizeof(double) * (size_t)N);
    bl_d2_4(u, lap, N, inv12dx2);
    for (int i = 0; i < N; i++) {
        du[i] = w[i];
        dw[i] = c2 * lap[i] - 2.0 * g * w[i];
    }
    free(lap);
}

static void step(const BlRun *r, double *state, double t0, double t1) {
    double seg = t1 - t0;
    if (seg <= 0.0) return;
    int N = r->N;
    double dx = 1.0 / (double)N, c2 = r->c * r->c, g = r->g;
    double inv12dx2 = 1.0 / (12.0 * dx * dx);
    int nst = (int)ceil(seg / (OVER_NU * dx / r->c) - 1e-12); /* WRONG: oversized Courant */
    if (nst < 1) nst = 1;
    double dts = seg / nst;
    double *u = state, *w = state + N;
    size_t nb = sizeof(double) * (size_t)N;
    double *k1u = malloc(nb), *k1w = malloc(nb), *k2u = malloc(nb), *k2w = malloc(nb);
    double *k3u = malloc(nb), *k3w = malloc(nb), *k4u = malloc(nb), *k4w = malloc(nb);
    double *tu = malloc(nb), *tw = malloc(nb);
    for (int s = 0; s < nst; s++) {
        rhs(u, w, k1u, k1w, N, c2, g, inv12dx2);
        for (int i = 0; i < N; i++) { tu[i] = u[i] + 0.5 * dts * k1u[i]; tw[i] = w[i] + 0.5 * dts * k1w[i]; }
        rhs(tu, tw, k2u, k2w, N, c2, g, inv12dx2);
        for (int i = 0; i < N; i++) { tu[i] = u[i] + 0.5 * dts * k2u[i]; tw[i] = w[i] + 0.5 * dts * k2w[i]; }
        rhs(tu, tw, k3u, k3w, N, c2, g, inv12dx2);
        for (int i = 0; i < N; i++) { tu[i] = u[i] + dts * k3u[i]; tw[i] = w[i] + dts * k3w[i]; }
        rhs(tu, tw, k4u, k4w, N, c2, g, inv12dx2);
        double sc = dts / 6.0;
        for (int i = 0; i < N; i++) {
            u[i] += sc * (k1u[i] + 2.0 * k2u[i] + 2.0 * k3u[i] + k4u[i]);
            w[i] += sc * (k1w[i] + 2.0 * k2w[i] + 2.0 * k3w[i] + k4w[i]);
        }
    }
    free(k1u); free(k1w); free(k2u); free(k2w); free(k3u); free(k3w);
    free(k4u); free(k4w); free(tu); free(tw);
}

int main(int argc, char **argv) { return bl_run_main(argc, argv, step); }
