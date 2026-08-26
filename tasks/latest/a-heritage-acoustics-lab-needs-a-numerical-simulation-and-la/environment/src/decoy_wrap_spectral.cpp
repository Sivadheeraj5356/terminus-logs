#include "decoy_wrap_spectral.h"

double decoy_wrap_spectral_smooth(double mag, double *state) {
    const double y = 0.15 * mag + 0.85 * state[0];
    state[0] = y;
    return y;
}
