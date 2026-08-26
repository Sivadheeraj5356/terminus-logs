#include "scheme.h"

/* Time integrator for the damped wave u_tt + 2 g u_t = c^2 u_xx on the periodic
 * grid x_i = i/N. The state array of length 2N holds the displacement in
 * state[0 .. N-1] and its time derivative u_t in state[N .. 2N-1].
 *
 * Starter stub: it performs no time evolution, so the reported field is just the
 * initial data (with zero velocity) repeated at every snapshot. Replace the body
 * with a scheme that advances the displacement and velocity in place from t0 to
 * t1, choosing stable sub-steps from the Courant number m->nu, so the emitted
 * field tracks the true damped solution and refines toward it as the grid is
 * refined. */
void scheme_advance(const Model *m, double *state, double t0, double t1) {
    (void)m;
    (void)state;
    (void)t0;
    (void)t1;
    /* TODO: advance the displacement and velocity on the grid from t0 to t1. */
}
