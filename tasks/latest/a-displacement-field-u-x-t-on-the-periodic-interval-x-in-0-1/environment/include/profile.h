#ifndef TRANSPORT_PROFILE_H
#define TRANSPORT_PROFILE_H

#include "model.h"

/* Evaluate one component's initial profile u0_c(x) from its descriptor at a
 * single point. The Gaussian uses the nearest periodic image on the unit
 * circle. */
double profile_eval(const Profile *p, double x);

/* Sample one component's profile onto the grid x[0..N-1], writing into the
 * length-N segment dst[0..N-1]. */
void profile_sample(const Profile *p, const double *x, double *dst, int N);

#endif /* TRANSPORT_PROFILE_H */
