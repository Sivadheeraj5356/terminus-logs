#ifndef TOFLAB_RECONCILE_H
#define TOFLAB_RECONCILE_H

#include "markdown.h"
#include "matrix.h"

#include <jansson.h>
#include <stddef.h>

#define MATCH_WINDOW_DA 0.015
#define K_SIGMA 2.5
#define LOCK_RATIO 0.4
#define MONOTONICITY_EPS 1e-9
#define GLS_OUTLIER_THRESH 11.344866730144373
#define D2_TIE_EPS 1e-12

typedef struct {
    char peak_id[64];
    double tof_us;
    double tof_sigma_us;
    double corrected_da;
    double sigma_corr_da;
    char catalog_id[64];
    int has_catalog;
    double catalog_da;
    double residual_da;
    double z_score;
    int accepted;
    char reject_reason[32];
} PeakResult;

typedef struct {
    Vec3 theta;
    Mat3 cov;
    char source[40];
    double interval_lo;
    double interval_hi;
    char **used_keys;
    size_t used_count;
    RejectedList rejected;
    PeakResult *peaks;
    size_t peak_count;
    int matched;
    int accepted;
    int rejected_count;
    int no_match;
    int outlier;
    double weighted_rms_z;
    int has_weighted_rms_z;
    double max_abs_z;
    int has_max_abs_z;
} ReconcileResult;

void reconcile_result_free(ReconcileResult *r);

int candidate_is_monotonic(const Vec3 *theta, double tof_lo, double tof_hi);

/* Build reconciled axis + peak table. Returns 0 on success. */
int reconcile_run(const char *run_id, json_t *calibration, json_t *peaks,
                  json_t *catalog, const LabCandidateList *labs,
                  RejectedList *parse_rejected, ReconcileResult *out);

#endif
