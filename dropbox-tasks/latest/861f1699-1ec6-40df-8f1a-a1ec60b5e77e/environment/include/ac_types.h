#ifndef AC_TYPES_H
#define AC_TYPES_H

#include "ac_limits.h"

struct ac_ct_volume {
    int nx;
    int ny;
    unsigned char voxels[AC_NX * AC_NY];
};

struct ac_speed_map {
    int nx;
    int ny;
    float c[AC_NX * AC_NY];
};

struct ac_pressure_trace {
    int sample_count;
    float samples[AC_MAX_SAMPLES];
};

struct ac_formant_report {
    char profile[AC_MAX_PROFILE];
    int sample_rate_hz;
    int formant_count;
    double formants_hz[AC_MAX_FORMANTS];
    double peak_prominence_db;
    char pressure_digest[65];
    char cavity_speed_digest[65];
};

#endif
