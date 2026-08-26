#include "harness.h"

/* Second-order time: the correct fourth-order space stencil, but the time march
 * is velocity-Verlet (a second-order-in-time integrator) with the linear damping
 * handled implicitly, instead of the fourth-order Runge-Kutta step. Because the
 * step is tied to the spacing, the time error is O(dx^2), so at a fixed Courant
 * number the refinement slope stalls near two and it fails both the fourth-order
 * L2 band and the slope band. This is the order-balance trap: the space stencil
 * alone is high order, but the time integration is not. */
static void step(const BlRun *r, double *state, double t0, double t1) {
    double seg = t1 - t0;
    if (seg <= 0.0) return;
    int N = r->N;
    double dx = 1.0 / (double)N, c2 = r->c * r->c, g = r->g;
    double inv12dx2 = 1.0 / (12.0 * dx * dx);
    int nst = (int)ceil(seg / (r->nu * dx / r->c) - 1e-12);
    if (nst < 1) nst = 1;
    double dts = seg / nst;
    double *u = state, *w = state + N;
    size_t nb = sizeof(double) * (size_t)N;
    double *lap = malloc(nb), *acc = malloc(nb), *lap1 = malloc(nb);
    for (int s = 0; s < nst; s++) {
        bl_d2_4(u, lap, N, inv12dx2);
        for (int i = 0; i < N; i++) acc[i] = c2 * lap[i] - 2.0 * g * w[i];
        for (int i = 0; i < N; i++) u[i] += dts * w[i] + 0.5 * dts * dts * acc[i];
        bl_d2_4(u, lap1, N, inv12dx2);
        double denom = 1.0 + g * dts;
        for (int i = 0; i < N; i++)
            w[i] = (w[i] + 0.5 * dts * (acc[i] + c2 * lap1[i])) / denom;
    }
    free(lap); free(acc); free(lap1);
}

int main(int argc, char **argv) { return bl_run_main(argc, argv, step); }
