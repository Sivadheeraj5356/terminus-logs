/* Starter kernel: an intentionally-incomplete plain-double implementation.
 * It loses all accuracy under the catastrophic cancellation this task targets.
 * Replace the body of erfsum_weighted_sum with a correct implementation. */
#include "erfsum.h"

#include <math.h>
#include <stdlib.h>

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

static double erf_double(double x) {
    double x2 = x * x;
    double b = x;
    double s = x;
    for (int n = 1; n < 600; n++) {
        b *= -x2 / (double)n;
        s += b / (2.0 * n + 1.0);
        if (fabs(b) < fabs(s) * 1e-18) {
            break;
        }
    }
    return (2.0 / sqrt(M_PI)) * s;
}

void erfsum_weighted_sum(int n, const char *const *c, const char *const *x, double *out) {
    double s = 0.0;
    for (int i = 0; i < n; i++) {
        double ci = strtod(c[i], NULL);
        double xi = strtod(x[i], NULL);
        s += ci * erf_double(xi);
    }
    *out = s;
}
