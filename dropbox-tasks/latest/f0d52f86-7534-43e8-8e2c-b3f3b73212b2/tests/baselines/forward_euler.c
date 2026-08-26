#include "harness.h"

/* First-order time: the correct fourth-order space stencil, but the time march is
 * explicit forward Euler instead of the fourth-order Runge-Kutta step. The time
 * error is O(dx) at a fixed Courant number, so the refinement slope stalls near
 * one and the scheme misses both the fourth-order L2 band and the slope band;
 * forward Euler on this oscillatory system is also anti-dissipative and tends to
 * amplify, so it may additionally break finiteness or energy. */
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
    double *lap = malloc(nb), *un = malloc(nb), *wn = malloc(nb);
    for (int s = 0; s < nst; s++) {
        bl_d2_4(u, lap, N, inv12dx2);
        for (int i = 0; i < N; i++) {
            un[i] = u[i] + dts * w[i];
            wn[i] = w[i] + dts * (c2 * lap[i] - 2.0 * g * w[i]);
        }
        memcpy(u, un, nb);
        memcpy(w, wn, nb);
    }
    free(lap); free(un); free(wn);
}

int main(int argc, char **argv) { return bl_run_main(argc, argv, step); }
