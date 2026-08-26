#ifndef CRYOVAC_TYPES_H
#define CRYOVAC_TYPES_H

#define CV_NAME 32
#define CV_MAX_STEPS 64
#define CV_MAX_CAL 64

#define CV_LEG_DESCEND 0
#define CV_LEG_ASCEND 1

typedef struct {
    char name[CV_NAME];
    double a;
    double b;
    int condensable;
    double T_cond;
    double T_freeze;
    double T_thaw;
    double P_vap_ref;
    double T_vap_ref;
    double L_vap;
    double film_site_beta;
    double kappa_film; /* m^3 free-volume lost per mol condensate */
    double vmin_frac;  /* floor on V_free / V_geom */
} CvSpecies;

typedef struct {
    double K_n2;
    double K_he;
    double n_sites;
} CvSorption;

typedef struct {
    int seq;
    int valid;
    int universal;
    int leg; /* -1 = any */
    int requires_prev_seq; /* -1 = none */
    double t_min;
    double t_max;
    double K_n2;
    double K_he;
    double n_sites;
} CvCalRow;

typedef struct {
    int count;
    CvCalRow rows[CV_MAX_CAL];
} CvCalTable;

typedef struct {
    int max_solver_iters;
    double ads_tol;
    double cond_tol;
} CvSolverCfg;

typedef struct {
    double t;
    double temp_k;
    double p_total;
    double n_gas_n2;
    double n_gas_he;
    double n_ads_n2;
    double n_ads_he;
    double n_cond_n2;
    double x_he;
    int frozen;
    int cal_seq;
    int solver_iters;
    int thermal_leg;
    const char *regime;
} CvStepOut;

typedef struct {
    CvSpecies n2;
    CvSpecies he;
    CvCalTable cal;
    CvSorption sorption;
    CvSolverCfg solver;
    int active_cal_seq;
    int prev_cal_seq;
    double volume_m3;
    double n_gas_n2;
    double n_gas_he;
    double n_ads_n2;
    double n_ads_he;
    double n_cond_n2;
    int frozen;
    int wall_hold; /* lock N2 ads on thaw station */
    int freeze_events;
    int condensation_events;
    int has_prev_temp;
    double prev_temp_k;
    int prev_leg;
    int sticky_seq;
} CvChamber;

#endif
