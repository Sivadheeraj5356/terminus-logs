/* Wrong baseline: sixth-order in space, only fourth-order in time.
 *
 * The spatial operator is the correct sixth-order 7-point second-derivative
 * stencil, but the time march is classical fourth-order Runge-Kutta. Because the
 * step size follows the Courant number (dt ~ dx), the fourth-order time error
 * O(dt^4) = O(dx^4) dominates the sixth-order spatial error, so the joint L2
 * refinement slope is only about four. The scheme is conservative, dissipative,
 * finite, and matches the reference in absolute terms, so it passes every
 * physical path; it is rejected solely by the sixth-order accuracy band, proving
 * the requirement is on the whole scheme (space AND time), not the stencil alone.
 */
#include "harness.h"

static void rhs(const BlRun *r, const double *u, const double *w, double *du,
                double *dw, double invdx2, double *tmp) {
    int N = r->N;
    double c2 = r->c * r->c, g = r->g;
    bl_d2_6(u, tmp, N, invdx2);
    for (int i = 0; i < N; i++) {
        du[i] = w[i];
        dw[i] = c2 * tmp[i] - 2.0 * g * w[i];
    }
}

static void bl_step(const BlRun *r, double *state, double t0, double t1) {
    double seg = t1 - t0;
    if (seg <= 0.0) {
        return;
    }
    int N = r->N;
    double dx = 1.0 / (double)N;
    double invdx2 = 1.0 / (dx * dx);
    double dt_nom = r->nu * dx / r->c;
    int nst = (int)ceil(seg / dt_nom - 1e-12);
    if (nst < 1) {
        nst = 1;
    }
    double dt = seg / (double)nst;
    double *u = state, *w = state + N;

    double *k1u = malloc(N * sizeof(double)), *k1w = malloc(N * sizeof(double));
    double *k2u = malloc(N * sizeof(double)), *k2w = malloc(N * sizeof(double));
    double *k3u = malloc(N * sizeof(double)), *k3w = malloc(N * sizeof(double));
    double *k4u = malloc(N * sizeof(double)), *k4w = malloc(N * sizeof(double));
    double *tu = malloc(N * sizeof(double)), *tw = malloc(N * sizeof(double));
    double *tmp = malloc(N * sizeof(double));

    for (int s = 0; s < nst; s++) {
        rhs(r, u, w, k1u, k1w, invdx2, tmp);
        for (int i = 0; i < N; i++) {
            tu[i] = u[i] + 0.5 * dt * k1u[i];
            tw[i] = w[i] + 0.5 * dt * k1w[i];
        }
        rhs(r, tu, tw, k2u, k2w, invdx2, tmp);
        for (int i = 0; i < N; i++) {
            tu[i] = u[i] + 0.5 * dt * k2u[i];
            tw[i] = w[i] + 0.5 * dt * k2w[i];
        }
        rhs(r, tu, tw, k3u, k3w, invdx2, tmp);
        for (int i = 0; i < N; i++) {
            tu[i] = u[i] + dt * k3u[i];
            tw[i] = w[i] + dt * k3w[i];
        }
        rhs(r, tu, tw, k4u, k4w, invdx2, tmp);
        double a = dt / 6.0;
        for (int i = 0; i < N; i++) {
            u[i] += a * (k1u[i] + 2.0 * k2u[i] + 2.0 * k3u[i] + k4u[i]);
            w[i] += a * (k1w[i] + 2.0 * k2w[i] + 2.0 * k3w[i] + k4w[i]);
        }
    }

    free(k1u);
    free(k1w);
    free(k2u);
    free(k2w);
    free(k3u);
    free(k3w);
    free(k4u);
    free(k4w);
    free(tu);
    free(tw);
    free(tmp);
}

int main(int argc, char **argv) {
    return bl_run_main(argc, argv, bl_step);
}
