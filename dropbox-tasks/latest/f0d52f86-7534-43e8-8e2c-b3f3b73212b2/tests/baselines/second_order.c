#include "harness.h"

/* Second-order space: the correct RK4 time integration and damping, but the
 * Laplacian is the standard 3-point second-order stencil
 *   (u_{i-1} - 2 u_i + u_{i+1}) / dx^2
 * instead of the fourth-order 5-point stencil. Stable, conservative, energy
 * non-increasing, and it passes every metamorphic relation, but its error decays
 * only as the square of the grid spacing, so it falls below the fourth-order L2
 * band and the refinement-slope band and earns reward 0. */
static void rhs(const double *u, const double *w, double *du, double *dw, int N,
                double c2, double g, double invdx2) {
    for (int i = 0; i < N; i++) {
        int im1 = (i - 1 + N) % N, ip1 = (i + 1) % N;
        double lap = (u[im1] - 2.0 * u[i] + u[ip1]) * invdx2;
        du[i] = w[i];
        dw[i] = c2 * lap - 2.0 * g * w[i];
    }
}

static void step(const BlRun *r, double *state, double t0, double t1) {
    double seg = t1 - t0;
    if (seg <= 0.0) return;
    int N = r->N;
    double dx = 1.0 / (double)N, c2 = r->c * r->c, g = r->g;
    double invdx2 = 1.0 / (dx * dx);
    int nst = (int)ceil(seg / (r->nu * dx / r->c) - 1e-12);
    if (nst < 1) nst = 1;
    double dts = seg / nst;
    double *u = state, *w = state + N;
    size_t nb = sizeof(double) * (size_t)N;
    double *k1u = malloc(nb), *k1w = malloc(nb), *k2u = malloc(nb), *k2w = malloc(nb);
    double *k3u = malloc(nb), *k3w = malloc(nb), *k4u = malloc(nb), *k4w = malloc(nb);
    double *tu = malloc(nb), *tw = malloc(nb);
    for (int s = 0; s < nst; s++) {
        rhs(u, w, k1u, k1w, N, c2, g, invdx2);
        for (int i = 0; i < N; i++) { tu[i] = u[i] + 0.5 * dts * k1u[i]; tw[i] = w[i] + 0.5 * dts * k1w[i]; }
        rhs(tu, tw, k2u, k2w, N, c2, g, invdx2);
        for (int i = 0; i < N; i++) { tu[i] = u[i] + 0.5 * dts * k2u[i]; tw[i] = w[i] + 0.5 * dts * k2w[i]; }
        rhs(tu, tw, k3u, k3w, N, c2, g, invdx2);
        for (int i = 0; i < N; i++) { tu[i] = u[i] + dts * k3u[i]; tw[i] = w[i] + dts * k3w[i]; }
        rhs(tu, tw, k4u, k4w, N, c2, g, invdx2);
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
