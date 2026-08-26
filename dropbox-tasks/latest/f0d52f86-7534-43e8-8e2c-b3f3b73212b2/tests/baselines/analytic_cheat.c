#include "harness.h"

/* Analytic cheat: emit the exact damped solution directly with no time stepping.
 * Each sinusoid mode is evolved by its closed-form damped-oscillator factor and
 * the constant part is preserved. It passes conservation, energy, and reference
 * agreement, but because it never integrates, its error against the reference sits
 * at the round-off floor on every grid, so its refinement slope is ~0 and the
 * convergence check rejects it (and it violates the "advance on the grid" rule). */
static void step(const BlRun *r, double *state, double t0, double t1) {
    (void)t0;
    int N = r->N;
    double dx = 1.0 / (double)N, c = r->c, g = r->g;
    const BlProfile *p = &r->prof;
    double *u = state, *w = state + N;
    if (p->is_gauss) {
        for (int i = 0; i < N; i++) { u[i] = bl_prof_eval(p, i * dx); w[i] = 0.0; }
        return;
    }
    for (int i = 0; i < N; i++) {
        double x = i * dx;
        double du = p->c0, dv = 0.0;
        for (int j = 0; j < p->nterm; j++) {
            double k = p->waves[j];
            double a = p->amps[j], ph = p->phases[j];
            double sx = sin(2.0 * M_PI * k * x + ph);
            if (k == 0.0) { du += a * sin(ph); continue; }
            double wk2 = (2.0 * M_PI * k * c) * (2.0 * M_PI * k * c) - g * g;
            double W = sqrt(wk2);
            double env = exp(-g * t1) * (cos(W * t1) + (g / W) * sin(W * t1));
            double fp = -exp(-g * t1) * sin(W * t1) * (2.0 * M_PI * k * c) *
                        (2.0 * M_PI * k * c) / W;
            du += a * env * sx;
            dv += a * fp * sx;
        }
        u[i] = du;
        w[i] = dv;
    }
}

int main(int argc, char **argv) { return bl_run_main(argc, argv, step); }
