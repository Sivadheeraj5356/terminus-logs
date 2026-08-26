/* Fairness baseline: a genuinely independent valid sixth-order scheme.
 *
 * Same sixth-order 7-point spatial stencil, but advanced by Luther's seven-stage
 * sixth-order Runge-Kutta method instead of the oracle's truncated-exponential
 * integrator. Both space and time are sixth order, so at a fixed Courant number
 * the refinement slope is ~6 and every physical and accuracy path is satisfied.
 * This must EARN full reward: it proves the accuracy band rewards any correct
 * sixth-order scheme rather than pinning the specific oracle time integrator.
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
    double a = sqrt(21.0);
    double *u = state, *w = state + N;

    double *k1u = malloc(N * sizeof(double)), *k1w = malloc(N * sizeof(double));
    double *k2u = malloc(N * sizeof(double)), *k2w = malloc(N * sizeof(double));
    double *k3u = malloc(N * sizeof(double)), *k3w = malloc(N * sizeof(double));
    double *k4u = malloc(N * sizeof(double)), *k4w = malloc(N * sizeof(double));
    double *k5u = malloc(N * sizeof(double)), *k5w = malloc(N * sizeof(double));
    double *k6u = malloc(N * sizeof(double)), *k6w = malloc(N * sizeof(double));
    double *k7u = malloc(N * sizeof(double)), *k7w = malloc(N * sizeof(double));
    double *tu = malloc(N * sizeof(double)), *tw = malloc(N * sizeof(double));
    double *tmp = malloc(N * sizeof(double));

    for (int s = 0; s < nst; s++) {
        rhs(r, u, w, k1u, k1w, invdx2, tmp);
        for (int i = 0; i < N; i++) {
            tu[i] = u[i] + dt * k1u[i];
            tw[i] = w[i] + dt * k1w[i];
        }
        rhs(r, tu, tw, k2u, k2w, invdx2, tmp);
        for (int i = 0; i < N; i++) {
            tu[i] = u[i] + dt * (3.0 * k1u[i] + k2u[i]) / 8.0;
            tw[i] = w[i] + dt * (3.0 * k1w[i] + k2w[i]) / 8.0;
        }
        rhs(r, tu, tw, k3u, k3w, invdx2, tmp);
        for (int i = 0; i < N; i++) {
            tu[i] = u[i] + dt * (8.0 * k1u[i] + 2.0 * k2u[i] + 8.0 * k3u[i]) / 27.0;
            tw[i] = w[i] + dt * (8.0 * k1w[i] + 2.0 * k2w[i] + 8.0 * k3w[i]) / 27.0;
        }
        rhs(r, tu, tw, k4u, k4w, invdx2, tmp);
        for (int i = 0; i < N; i++) {
            tu[i] = u[i] + dt *
                               (3.0 * (3.0 * a - 7.0) * k1u[i] -
                                8.0 * (7.0 - a) * k2u[i] +
                                48.0 * (7.0 - a) * k3u[i] -
                                3.0 * (21.0 - a) * k4u[i]) /
                               392.0;
            tw[i] = w[i] + dt *
                               (3.0 * (3.0 * a - 7.0) * k1w[i] -
                                8.0 * (7.0 - a) * k2w[i] +
                                48.0 * (7.0 - a) * k3w[i] -
                                3.0 * (21.0 - a) * k4w[i]) /
                               392.0;
        }
        rhs(r, tu, tw, k5u, k5w, invdx2, tmp);
        for (int i = 0; i < N; i++) {
            tu[i] = u[i] + dt *
                               (-5.0 * (231.0 + 51.0 * a) * k1u[i] -
                                40.0 * (7.0 + a) * k2u[i] - 320.0 * a * k3u[i] +
                                3.0 * (21.0 + 121.0 * a) * k4u[i] +
                                392.0 * (6.0 + a) * k5u[i]) /
                               1960.0;
            tw[i] = w[i] + dt *
                               (-5.0 * (231.0 + 51.0 * a) * k1w[i] -
                                40.0 * (7.0 + a) * k2w[i] - 320.0 * a * k3w[i] +
                                3.0 * (21.0 + 121.0 * a) * k4w[i] +
                                392.0 * (6.0 + a) * k5w[i]) /
                               1960.0;
        }
        rhs(r, tu, tw, k6u, k6w, invdx2, tmp);
        for (int i = 0; i < N; i++) {
            tu[i] = u[i] + dt *
                               (15.0 * (22.0 + 7.0 * a) * k1u[i] + 120.0 * k2u[i] +
                                40.0 * (7.0 * a - 5.0) * k3u[i] -
                                63.0 * (3.0 * a - 2.0) * k4u[i] -
                                14.0 * (49.0 + 9.0 * a) * k5u[i] +
                                70.0 * (7.0 - a) * k6u[i]) /
                               180.0;
            tw[i] = w[i] + dt *
                               (15.0 * (22.0 + 7.0 * a) * k1w[i] + 120.0 * k2w[i] +
                                40.0 * (7.0 * a - 5.0) * k3w[i] -
                                63.0 * (3.0 * a - 2.0) * k4w[i] -
                                14.0 * (49.0 + 9.0 * a) * k5w[i] +
                                70.0 * (7.0 - a) * k6w[i]) /
                               180.0;
        }
        rhs(r, tu, tw, k7u, k7w, invdx2, tmp);
        for (int i = 0; i < N; i++) {
            u[i] += dt *
                    (9.0 * k1u[i] + 64.0 * k3u[i] + 49.0 * k5u[i] +
                     49.0 * k6u[i] + 9.0 * k7u[i]) /
                    180.0;
            w[i] += dt *
                    (9.0 * k1w[i] + 64.0 * k3w[i] + 49.0 * k5w[i] +
                     49.0 * k6w[i] + 9.0 * k7w[i]) /
                    180.0;
        }
    }

    free(k1u); free(k1w); free(k2u); free(k2w); free(k3u); free(k3w);
    free(k4u); free(k4w); free(k5u); free(k5w); free(k6u); free(k6w);
    free(k7u); free(k7w); free(tu); free(tw); free(tmp);
}

int main(int argc, char **argv) {
    return bl_run_main(argc, argv, bl_step);
}
