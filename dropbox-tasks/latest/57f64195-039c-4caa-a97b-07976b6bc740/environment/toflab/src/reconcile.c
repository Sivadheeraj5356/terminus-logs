#include "reconcile.h"
#include "assignment.h"

#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>

void reconcile_result_free(ReconcileResult *r) {
    if (!r) {
        return;
    }
    if (r->used_keys) {
        for (size_t i = 0; i < r->used_count; i++) {
            free(r->used_keys[i]);
        }
        free(r->used_keys);
    }
    rejected_list_free(&r->rejected);
    free(r->peaks);
    memset(r, 0, sizeof(*r));
}

int candidate_is_monotonic(const Vec3 *theta, double tof_lo, double tof_hi) {
    double k = theta->v[0];
    double t0 = theta->v[1];
    double q = theta->v[2];

    double min_mp = INFINITY;
    double points[3];
    int n = 0;
    points[n++] = tof_lo;
    points[n++] = tof_hi;
    if (fabs(q) > 0.0) {
        double dt = -k / (3.0 * q);
        double t = t0 + dt;
        if (t >= tof_lo && t <= tof_hi) {
            points[n++] = t;
        }
    }
    for (int i = 0; i < n; i++) {
        double dt = points[i] - t0;
        double mp = 2.0 * k * dt + 3.0 * q * dt * dt;
        if (mp < min_mp) {
            min_mp = mp;
        }
    }
    return min_mp > MONOTONICITY_EPS;
}

static int parse_coeff_block(json_t *block, Vec3 *theta, Mat3 *cov, char *id,
                             size_t id_cap) {
    if (!json_is_object(block)) {
        return -1;
    }
    const char *cid = json_string_value(json_object_get(block, "candidate_id"));
    if (!cid) {
        return -1;
    }
    snprintf(id, id_cap, "%s", cid);

    json_t *jk = json_object_get(block, "k");
    json_t *jt0 = json_object_get(block, "t0");
    json_t *jq = json_object_get(block, "q");
    json_t *jsk = json_object_get(block, "sigma_k");
    json_t *jst0 = json_object_get(block, "sigma_t0");
    json_t *jsq = json_object_get(block, "sigma_q");
    json_t *jrkt0 = json_object_get(block, "rho_k_t0");
    json_t *jrkq = json_object_get(block, "rho_k_q");
    json_t *jrt0q = json_object_get(block, "rho_t0_q");
    const char *ku = json_string_value(json_object_get(block, "k_units"));
    const char *tu = json_string_value(json_object_get(block, "t0_units"));
    const char *qu = json_string_value(json_object_get(block, "q_units"));
    if (!json_is_number(jk) || !json_is_number(jt0) || !json_is_number(jq) ||
        !json_is_number(jsk) || !json_is_number(jst0) || !json_is_number(jsq) ||
        !json_is_number(jrkt0) || !json_is_number(jrkq) || !json_is_number(jrt0q) ||
        !ku || !tu || !qu) {
        return -1;
    }

    double k = json_number_value(jk);
    double t0 = json_number_value(jt0);
    double q = json_number_value(jq);
    double sk = json_number_value(jsk);
    double st0 = json_number_value(jst0);
    double sq = json_number_value(jsq);
    double rkt0 = json_number_value(jrkt0);
    double rkq = json_number_value(jrkq);
    double rt0q = json_number_value(jrt0q);

    if (!isfinite(k) || !isfinite(t0) || !isfinite(q) || !isfinite(sk) ||
        !isfinite(st0) || !isfinite(sq) || !isfinite(rkt0) || !isfinite(rkq) ||
        !isfinite(rt0q)) {
        return -1;
    }
    if (!(sk > 0.0) || !(st0 > 0.0) || !(sq > 0.0)) {
        return -1;
    }
    if (rkt0 < -1.0 || rkt0 > 1.0 || rkq < -1.0 || rkq > 1.0 || rt0q < -1.0 ||
        rt0q > 1.0) {
        return -1;
    }

    double sk_s = 1.0, st0_s = 1.0, sq_s = 1.0;
    if (!strcasecmp(ku, "Da_per_us2") || !strcasecmp(ku, "Da/us^2")) {
        sk_s = 1.0;
    } else if (!strcasecmp(ku, "mDa_per_us2") || !strcasecmp(ku, "mDa/us^2")) {
        sk_s = 1.0 / 1000.0;
    } else {
        return -1;
    }
    if (!strcasecmp(tu, "us")) {
        st0_s = 1.0;
    } else if (!strcasecmp(tu, "ns")) {
        st0_s = 1.0 / 1000.0;
    } else {
        return -1;
    }
    if (!strcasecmp(qu, "Da_per_us3") || !strcasecmp(qu, "Da/us^3")) {
        sq_s = 1.0;
    } else {
        return -1;
    }

    theta->v[0] = k;
    theta->v[1] = t0;
    theta->v[2] = q;
    cov_from_sigmas(cov, sk, st0, sq, rkt0, rkq, rt0q);
    apply_unit_scale(theta, cov, sk_s, st0_s, sq_s);
    if (!mat3_is_spd(cov)) {
        return -1;
    }
    return 0;
}

static int cmp_strptr(const void *a, const void *b) {
    const char *const *sa = a;
    const char *const *sb = b;
    return strcmp(*sa, *sb);
}

static int cmp_rejected(const void *a, const void *b) {
    const RejectedCandidate *ra = a;
    const RejectedCandidate *rb = b;
    int c = strcmp(ra->candidate_key, rb->candidate_key);
    if (c) {
        return c;
    }
    return strcmp(ra->reason, rb->reason);
}

static int cmp_peak(const void *a, const void *b) {
    const PeakResult *pa = a;
    const PeakResult *pb = b;
    return strcmp(pa->peak_id, pb->peak_id);
}

static double mass_at(const Vec3 *theta, double tof) {
    double dt = tof - theta->v[1];
    return theta->v[0] * dt * dt + theta->v[2] * dt * dt * dt;
}

static double sigma_corr_at(const Vec3 *theta, const Mat3 *cov, double tof,
                            double sigma_tof_us) {
    double k = theta->v[0];
    double t0 = theta->v[1];
    double q = theta->v[2];
    double dt = tof - t0;
    double jk = dt * dt;
    double jt0 = -2.0 * k * dt - 3.0 * q * dt * dt;
    double jq = dt * dt * dt;
    double dm = 2.0 * k * dt + 3.0 * q * dt * dt;
    double s2 = (jk * jk) * cov->m[0][0] + (jt0 * jt0) * cov->m[1][1] +
                (jq * jq) * cov->m[2][2] + (dm * sigma_tof_us) * (dm * sigma_tof_us);
    if (!(s2 >= 0.0)) {
        return NAN;
    }
    return sqrt(s2);
}

typedef struct {
    char key[320];
    Vec3 theta;
    Mat3 cov;
    int is_api;
    int alive;
} WorkCand;

static int robust_gls(WorkCand *cands, size_t n, Vec3 *theta_out, Mat3 *cov_out,
                      RejectedList *rejected, char *source, size_t source_cap) {
    (void)rejected;
    /* Diagonal GLS / scalar IVW: invert only marginal variances. */
    Mat3 P;
    mat3_zero(&P);
    for (size_t i = 0; i < n; i++) {
        if (!cands[i].alive) {
            continue;
        }
        for (int d = 0; d < 3; d++) {
            double s2 = cands[i].cov.m[d][d];
            if (!(s2 > 0.0)) {
                return -1;
            }
            P.m[d][d] += 1.0 / s2;
        }
    }
    mat3_zero(cov_out);
    Vec3 acc;
    vec3_zero(&acc);
    for (int d = 0; d < 3; d++) {
        if (!(P.m[d][d] > 0.0)) {
            return -1;
        }
        cov_out->m[d][d] = 1.0 / P.m[d][d];
    }
    for (size_t i = 0; i < n; i++) {
        if (!cands[i].alive) {
            continue;
        }
        for (int d = 0; d < 3; d++) {
            acc.v[d] += (1.0 / cands[i].cov.m[d][d]) * cands[i].theta.v[d];
        }
    }
    for (int d = 0; d < 3; d++) {
        theta_out->v[d] = cov_out->m[d][d] * acc.v[d];
    }
    int lab_left = 0;
    for (size_t i = 0; i < n; i++) {
        if (cands[i].alive && !cands[i].is_api) {
            lab_left = 1;
        }
    }
    snprintf(source, source_cap, "%s", lab_left ? "robust_gls" : "api_only");
    return 0;
}

int reconcile_run(const char *run_id, json_t *calibration, json_t *peaks_doc,
                  json_t *catalog, const LabCandidateList *labs,
                  RejectedList *parse_rejected, ReconcileResult *out) {
    memset(out, 0, sizeof(*out));
    rejected_list_init(&out->rejected);

    const char *cal_run = json_string_value(json_object_get(calibration, "run_id"));
    const char *peak_run = json_string_value(json_object_get(peaks_doc, "run_id"));
    (void)cal_run;
    (void)peak_run;
    (void)run_id;

    json_t *active = json_object_get(calibration, "active");
    if (!active) {
        return -1;
    }
    Vec3 api_theta;
    Mat3 api_cov;
    char api_id[64];
    if (parse_coeff_block(active, &api_theta, &api_cov, api_id, sizeof(api_id)) !=
        0) {
        return -1;
    }
    char api_key[320];
    snprintf(api_key, sizeof(api_key), "instrument::%s", api_id);

    json_t *peaks_arr = json_object_get(peaks_doc, "peaks");
    if (!json_is_array(peaks_arr) || json_array_size(peaks_arr) == 0) {
        return -1;
    }
    size_t npeaks = json_array_size(peaks_arr);
    double tof_lo = INFINITY, tof_hi = -INFINITY;
    for (size_t i = 0; i < npeaks; i++) {
        json_t *p = json_array_get(peaks_arr, i);
        json_t *jt = json_object_get(p, "tof_us");
        if (!json_is_number(jt)) {
            return -1;
        }
        double t = json_number_value(jt);
        if (t < tof_lo) {
            tof_lo = t;
        }
        if (t > tof_hi) {
            tof_hi = t;
        }
    }
    out->interval_lo = tof_lo;
    out->interval_hi = tof_hi;

    if (!candidate_is_monotonic(&api_theta, tof_lo, tof_hi)) {
        return -1;
    }

    /* copy parse rejects */
    for (size_t i = 0; i < parse_rejected->count; i++) {
        rejected_list_push(&out->rejected, parse_rejected->items[i].candidate_key,
                           parse_rejected->items[i].reason);
    }

    LabCandidateList admissible;
    lab_list_init(&admissible);
    for (size_t i = 0; i < labs->count; i++) {
        const LabCandidate *c = &labs->items[i];
        lab_list_push(&admissible, c);
    }

    Vec3 theta;
    Mat3 cov;
    char source[40];

    if (admissible.count == 0) {
        theta = api_theta;
        cov = api_cov;
        snprintf(source, sizeof(source), "%s", "api_only");
        out->used_keys = malloc(sizeof(char *));
        out->used_keys[0] = strdup(api_key);
        out->used_count = 1;
    } else {
        double gmin = INFINITY;
        for (size_t i = 0; i < admissible.count; i++) {
            double g = mat3_gscale(&admissible.items[i].cov);
            if (g < gmin) {
                gmin = g;
            }
        }
        double gapi = mat3_gscale(&api_cov);
        if (gapi <= LOCK_RATIO * gmin) {
            theta = api_theta;
            cov = api_cov;
            snprintf(source, sizeof(source), "%s", "api_lock");
            out->used_keys = malloc(sizeof(char *));
            out->used_keys[0] = strdup(api_key);
            out->used_count = 1;
        } else {
            WorkCand *wc = calloc(admissible.count + 1, sizeof(WorkCand));
            snprintf(wc[0].key, sizeof(wc[0].key), "%s", api_key);
            wc[0].theta = api_theta;
            wc[0].cov = api_cov;
            wc[0].is_api = 1;
            wc[0].alive = 1;
            for (size_t i = 0; i < admissible.count; i++) {
                snprintf(wc[i + 1].key, sizeof(wc[i + 1].key), "%s",
                         admissible.items[i].candidate_key);
                wc[i + 1].theta = admissible.items[i].theta;
                wc[i + 1].cov = admissible.items[i].cov;
                wc[i + 1].is_api = 0;
                wc[i + 1].alive = 1;
            }
            if (robust_gls(wc, admissible.count + 1, &theta, &cov, &out->rejected,
                           source, sizeof(source)) != 0) {
                free(wc);
                lab_list_free(&admissible);
                return -1;
            }
            size_t used = 0;
            for (size_t i = 0; i < admissible.count + 1; i++) {
                if (wc[i].alive) {
                    used++;
                }
            }
            out->used_keys = calloc(used, sizeof(char *));
            out->used_count = 0;
            for (size_t i = 0; i < admissible.count + 1; i++) {
                if (wc[i].alive) {
                    out->used_keys[out->used_count++] = strdup(wc[i].key);
                }
            }
            free(wc);
        }
    }
    lab_list_free(&admissible);

    qsort(out->used_keys, out->used_count, sizeof(char *), cmp_strptr);
    if (out->rejected.count > 1) {
        qsort(out->rejected.items, out->rejected.count, sizeof(RejectedCandidate),
              cmp_rejected);
    }

    snprintf(out->source, sizeof(out->source), "%s", source);
    out->theta = theta;
    out->cov = cov;

    /* catalog */
    json_t *ions = json_object_get(catalog, "ions");
    if (!json_is_array(ions)) {
        return -1;
    }
    size_t nions = json_array_size(ions);
    if (nions > 16) {
        return -1;
    }
    char **ion_ids = calloc(nions ? nions : 1, sizeof(char *));
    double *ion_mz = calloc(nions ? nions : 1, sizeof(double));
    double *ion_sig = calloc(nions ? nions : 1, sizeof(double));
    for (size_t i = 0; i < nions; i++) {
        json_t *ion = json_array_get(ions, i);
        const char *iid = json_string_value(json_object_get(ion, "ion_id"));
        json_t *jmz = json_object_get(ion, "mz_da");
        json_t *js = json_object_get(ion, "sigma_da");
        if (!iid || !json_is_number(jmz) || !json_is_number(js)) {
            free(ion_ids);
            free(ion_mz);
            free(ion_sig);
            return -1;
        }
        double sig = json_number_value(js);
        if (!(sig > 0.0)) {
            free(ion_ids);
            free(ion_mz);
            free(ion_sig);
            return -1;
        }
        for (size_t j = 0; j < i; j++) {
            if (strcmp(ion_ids[j], iid) == 0) {
                for (size_t k = 0; k < i; k++) {
                    free(ion_ids[k]);
                }
                free(ion_ids);
                free(ion_mz);
                free(ion_sig);
                return -1;
            }
        }
        ion_ids[i] = strdup(iid);
        ion_mz[i] = json_number_value(jmz);
        ion_sig[i] = sig;
    }

    out->peaks = calloc(npeaks, sizeof(PeakResult));
    out->peak_count = npeaks;
    char **peak_ids = calloc(npeaks, sizeof(char *));
    AssignEdge *edges = calloc(npeaks * (nions ? nions : 1), sizeof(AssignEdge));
    size_t nedges = 0;

    for (size_t i = 0; i < npeaks; i++) {
        json_t *p = json_array_get(peaks_arr, i);
        const char *pid = json_string_value(json_object_get(p, "peak_id"));
        json_t *jt = json_object_get(p, "tof_us");
        json_t *jsn = json_object_get(p, "tof_sigma_ns");
        if (!pid || !json_is_number(jt) || !json_is_number(jsn)) {
            for (size_t k = 0; k < nions; k++) {
                free(ion_ids[k]);
            }
            free(ion_ids);
            free(ion_mz);
            free(ion_sig);
            free(peak_ids);
            free(edges);
            return -1;
        }
        PeakResult *pr = &out->peaks[i];
        snprintf(pr->peak_id, sizeof(pr->peak_id), "%s", pid);
        peak_ids[i] = pr->peak_id;
        pr->tof_us = json_number_value(jt);
        pr->tof_sigma_us = json_number_value(jsn) / 1000.0;
        pr->corrected_da = mass_at(&theta, pr->tof_us);
        pr->sigma_corr_da =
            sigma_corr_at(&theta, &cov, pr->tof_us, pr->tof_sigma_us);
        pr->has_catalog = 0;
        pr->accepted = 0;
        snprintf(pr->reject_reason, sizeof(pr->reject_reason), "%s", "no_match");

        for (size_t j = 0; j < nions; j++) {
            double res = pr->corrected_da - ion_mz[j];
            if (fabs(res) <= MATCH_WINDOW_DA) {
                double denom = pr->sigma_corr_da * pr->sigma_corr_da +
                               ion_sig[j] * ion_sig[j];
                edges[nedges].peak_index = (int)i;
                edges[nedges].ion_index = (int)j;
                edges[nedges].cost = (res * res) / denom;
                nedges++;
            }
        }
    }

    AssignResult asg;
    if (assign_peaks(edges, nedges, npeaks, nions,
                     (const char *const *)peak_ids,
                     (const char *const *)ion_ids, &asg) != 0) {
        for (size_t k = 0; k < nions; k++) {
            free(ion_ids[k]);
        }
        free(ion_ids);
        free(ion_mz);
        free(ion_sig);
        free(peak_ids);
        free(edges);
        return -1;
    }

    for (size_t i = 0; i < npeaks; i++) {
        PeakResult *pr = &out->peaks[i];
        int j = asg.peak_to_ion[i];
        if (j < 0) {
            out->no_match++;
            out->rejected_count++;
            continue;
        }
        pr->has_catalog = 1;
        snprintf(pr->catalog_id, sizeof(pr->catalog_id), "%s", ion_ids[j]);
        pr->catalog_da = ion_mz[j];
        pr->residual_da = pr->corrected_da - ion_mz[j];
        double denom =
            sqrt(pr->sigma_corr_da * pr->sigma_corr_da + ion_sig[j] * ion_sig[j]);
        pr->z_score = pr->residual_da / denom;
        out->matched++;
        if (fabs(pr->z_score) > K_SIGMA) {
            pr->accepted = 0;
            snprintf(pr->reject_reason, sizeof(pr->reject_reason), "%s", "outlier");
            out->outlier++;
            out->rejected_count++;
        } else {
            pr->accepted = 1;
            pr->reject_reason[0] = '\0';
            out->accepted++;
        }
    }

    if (out->matched > 0) {
        double sumz2 = 0.0;
        double maxabs = 0.0;
        for (size_t i = 0; i < npeaks; i++) {
            if (!out->peaks[i].has_catalog) {
                continue;
            }
            sumz2 += out->peaks[i].z_score * out->peaks[i].z_score;
            double a = fabs(out->peaks[i].z_score);
            if (a > maxabs) {
                maxabs = a;
            }
        }
        out->weighted_rms_z = sqrt(sumz2 / out->matched);
        out->has_weighted_rms_z = 1;
        out->max_abs_z = maxabs;
        out->has_max_abs_z = 1;
    }

    qsort(out->peaks, out->peak_count, sizeof(PeakResult), cmp_peak);

    assign_result_free(&asg);
    for (size_t k = 0; k < nions; k++) {
        free(ion_ids[k]);
    }
    free(ion_ids);
    free(ion_mz);
    free(ion_sig);
    free(peak_ids);
    free(edges);
    return 0;
}
