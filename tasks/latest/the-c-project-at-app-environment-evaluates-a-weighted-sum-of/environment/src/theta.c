#include "theta.h"

#include <math.h>
#include <stdlib.h>

/* Direct double-precision evaluation of theta3(z, q) = 1 + 2 sum q^(k^2) cos(2kz).
 * Accurate when the weighted terms of the final sum stay near the size of the
 * result, but it loses all significance once the terms are far larger than S. */
static double theta3_scalar(double z, double q) {
    double s = 1.0;
    for (int k = 1; k <= 400; k++) {
        double t = 2.0 * pow(q, (double)(k * k)) * cos(2.0 * (double)k * z);
        s += t;
        if (fabs(t) < 1e-18 && k > 4) break;
    }
    return s;
}

void theta3(int n, const char *const *c, const char *const *z,
            const char *const *q, double *out) {
    double acc = 0.0;
    for (int i = 0; i < n; i++) {
        acc += atof(c[i]) * theta3_scalar(atof(z[i]), atof(q[i]));
    }
    *out = acc;
}
