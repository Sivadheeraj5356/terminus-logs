#ifndef TELEGRAPH_SCHEME_H
#define TELEGRAPH_SCHEME_H

#include "model.h"

/* Time integrator for the periodic damped wave u_tt + 2 g u_t = c^2 u_xx.
 *
 * The evolving state lives in one array of length 2N (N = m->N) holding two
 * length-N halves: the displacement u in state[0 .. N-1] and its time derivative
 * u_t in state[N .. 2N-1], both sampled on the grid x_i = i/N. Advance the whole
 * state in place from time t0 to time t1 (with t1 >= t0). The routine must
 * sub-divide the interval into stable steps whose size follows the Courant number
 * m->nu, evolve the field forward on the grid rather than writing any closed-form
 * solution, and leave the advanced displacement and velocity in `state` for the
 * caller to snapshot. At the initial time the velocity half is zero because the
 * field is released from rest.
 *
 * This is the one routine the solver leaves unimplemented. Everything else in the
 * project -- input parsing, grid construction, initial-profile sampling, and CSV
 * output -- is already provided by the surrounding modules. */
void scheme_advance(const Model *m, double *state, double t0, double t1);

#endif /* TELEGRAPH_SCHEME_H */
