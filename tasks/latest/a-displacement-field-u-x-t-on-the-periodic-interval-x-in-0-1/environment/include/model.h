#ifndef TELEGRAPH_MODEL_H
#define TELEGRAPH_MODEL_H

/* Problem description for one run of the damped wave (telegraph) equation
 *
 *     u_tt + 2 g u_t = c^2 u_xx,   u(x, t) real,   x in [0, 1),   t >= 0,
 *
 * on the periodic unit interval, with wave speed c > 0, damping rate g > 0, and
 * the field released from rest (u_t(x, 0) = 0). Populated by config_load from the
 * JSON input; consumed by the driver and the time integrator. */

#define TEL_MAX_SNAPS 64
#define TEL_MAX_TERMS 64

typedef enum {
    PROFILE_GAUSSIAN = 0,
    PROFILE_SINSUM = 1
} ProfileKind;

/* Descriptor of the initial displacement profile u0(x). A periodic Gaussian is
 * given by its center and width; a sinusoid sum by a constant term plus matching
 * lists of amplitudes, integer wavenumbers, and phases. */
typedef struct {
    ProfileKind kind;
    double center;                 /* gaussian center */
    double width;                  /* gaussian width */
    double c0;                     /* sinsum constant term */
    int nterm;                     /* number of sinusoid terms */
    double amps[TEL_MAX_TERMS];    /* sinsum amplitudes */
    double waves[TEL_MAX_TERMS];   /* sinsum integer wavenumbers */
    double phases[TEL_MAX_TERMS];  /* sinsum phases */
} Profile;

typedef struct {
    double c;                      /* wave speed (c > 0) */
    double g;                      /* damping rate (g > 0) */
    int N;                         /* number of grid cells */
    double nu;                     /* Courant number nu = c dt / dx */
    double T;                      /* final time */
    int nsnap;                     /* number of snapshot times */
    double snaps[TEL_MAX_SNAPS];   /* snapshot times, increasing */
    Profile profile;               /* initial displacement; released from rest */
} Model;

#endif /* TELEGRAPH_MODEL_H */
