#include "cryovac/eos.h"

#include <math.h>

double cv_R(void) {
    return 8.314;
}

double cv_mix_a(double x1, double a1, double x2, double a2) {
    return x1 * x1 * a1 + x2 * x2 * a2 + 2.0 * x1 * x2 * ((a1 + a2) * 0.5);
}

double cv_mix_b(double x1, double b1, double x2, double b2) {
    return x1 * b1 + x2 * b2;
}

double cv_free_volume(const CvChamber *ch) {
    double v = ch->volume_m3 - ch->n2.kappa_film * ch->n_cond_n2;
    if (v <= 0.0) {
        v = ch->volume_m3 * 0.01;
    }
    return v;
}

double cv_pressure_binary(double n1, double n2, double V, double T,
                          const CvSpecies *s1, const CvSpecies *s2) {
    double n = n1 + n2;
    if (n <= 0.0 || V <= 0.0 || T <= 0.0) {
        return 0.0;
    }
    double x1 = n1 / n;
    double x2 = n2 / n;
    double a = cv_mix_a(x1, s1->a, x2, s2->a);
    double b = cv_mix_b(x1, s1->b, x2, s2->b);
    double denom = V - n * b;
    if (denom <= 0.0) {
        return 0.0;
    }
    return (n * cv_R() * T) / denom - a * n * n / (V * V);
}

double cv_fugacity(double p_i, double b_i, double P, double T) {
    if (T <= 0.0) {
        return 0.0;
    }
    (void)P;
    return p_i * exp(b_i * p_i / (cv_R() * T));
}
