#ifndef RECONCILE_B_H
#define RECONCILE_B_H

#include "ac_types.h"

struct ac_fdtd_state {
    float p[AC_NX * AC_NY];
    float p_old[AC_NX * AC_NY];
    ac_pressure_trace trace;
    int record_idx;
    int stride_counter;
};

int reconcile_b(const char *profile, const ac_speed_map *speed, ac_fdtd_state *state);

#endif
