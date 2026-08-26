#include "profile.h"

#include <math.h>

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

static double eval_gauss(double x, double center, double width) {
    double d = x - center;
    d = d - round(d); /* nearest periodic image on the unit circle */
    return exp(-(d / width) * (d / width));
}

double profile_eval(const Profile *p, double x) {
    if (p->kind == PROFILE_GAUSSIAN) {
        return eval_gauss(x, p->center, p->width);
    }
    double v = p->c0;
    for (int j = 0; j < p->nterm; j++) {
        v += p->amps[j] * sin(2.0 * M_PI * p->waves[j] * x + p->phases[j]);
    }
    return v;
}

void profile_sample(const Profile *p, const double *x, double *dst, int N) {
    for (int i = 0; i < N; i++) {
        dst[i] = profile_eval(p, x[i]);
    }
}
