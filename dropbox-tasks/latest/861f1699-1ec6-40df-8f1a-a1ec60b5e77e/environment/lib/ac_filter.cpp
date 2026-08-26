#include "ac_filter.h"

double ac_biquad_tick(double x, double *state) {
    const double y = 0.25 * x + 0.5 * state[0];
    state[0] = x;
    return y;
}
