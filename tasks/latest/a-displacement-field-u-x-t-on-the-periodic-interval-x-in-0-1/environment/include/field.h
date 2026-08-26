#ifndef TRANSPORT_FIELD_H
#define TRANSPORT_FIELD_H

/* Grid-field allocation and simple per-component diagnostics. The diagnostics
 * are for optional logging only; they never feed back into the time integrator.
 * A multi-component field of length m*N is stored component major: component c
 * occupies indices c*N .. c*N + N-1. */

/* Allocate a zero-initialized field of length n (aborts on OOM). */
double *field_alloc(int n);

/* Discrete mass sum(u_c)/N of one length-N component segment. */
double field_mass(const double *u_c, int N);

/* Minimum and maximum over one length-N component segment. */
void field_minmax(const double *u_c, int N, double *lo, double *hi);

#endif /* TRANSPORT_FIELD_H */
