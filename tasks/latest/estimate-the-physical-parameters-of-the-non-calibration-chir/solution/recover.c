#include "recover.h"

#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define MAX_PEAKS 4096
#define MAX_CANDIDATES 32768
#define MAX_CLUSTERS 128
#define PI 3.14159265358979323846

typedef struct {
    const ObservationBundle *bundle;
    const ObsWindow *window;
    const Instrument *instrument;
    double alias_hz;
    double power;
    double mid_s;
} Peak;

typedef struct {
    double f_hz;
    double weight;
    int peak_index;
} Candidate;

typedef struct {
    double center;
    double weight;
    int support;
    int used;
} Cluster;

static double corrected_time(double raw_t, const Instrument *inst) {
    return raw_t / (1.0 + inst->clock_ppm * 1e-6);
}

static double effective_rate(const Instrument *inst) {
    return inst->sample_rate_hz * (1.0 + inst->clock_ppm * 1e-6);
}

static double fold_alias(double f, double fs) {
    double r = fmod(f, fs);
    if (r < 0.0) r += fs;
    return r <= fs * 0.5 ? r : fs - r;
}

static double peak_power_at(const ObsWindow *win, const Instrument *inst, double alias_hz) {
    double re = 0.0;
    double im = 0.0;
    double mean = 0.0;
    for (uint16_t i = 0; i < win->present_count; i++) mean += win->value[i];
    if (win->present_count) mean /= (double)win->present_count;

    for (uint16_t i = 0; i < win->present_count; i++) {
        double t = corrected_time(win->time_s[i], inst);
        double x = win->value[i] - mean;
        double a = 2.0 * PI * alias_hz * t;
        re += x * cos(a);
        im -= x * sin(a);
    }
    return (re * re + im * im) / (double)(win->present_count ? win->present_count : 1);
}

static double refine_alias(const ObsWindow *win, const Instrument *inst, double alias_hz) {
    double best_f = alias_hz;
    double best_p = -1.0;
    for (int i = -24; i <= 24; i++) {
        double f = alias_hz + 0.25 * (double)i;
        if (f < 40.0 || f > effective_rate(inst) * 0.5) continue;
        double p = peak_power_at(win, inst, f);
        if (p > best_p) {
            best_p = p;
            best_f = f;
        }
    }
    return best_f;
}

static int peak_far_enough(const Peak *peaks, size_t begin, size_t end, double alias_hz) {
    for (size_t i = begin; i < end; i++) {
        if (fabs(peaks[i].alias_hz - alias_hz) < 45.0) return 0;
    }
    return 1;
}

static int cmp_peak_power(const void *a, const void *b) {
    const Peak *pa = (const Peak *)a;
    const Peak *pb = (const Peak *)b;
    return (pb->power > pa->power) - (pb->power < pa->power);
}

static int collect_peaks(const Catalog *catalog, const ObservationSet *observations, Peak *peaks, size_t *peak_count) {
    *peak_count = 0;
    for (size_t b = 0; b < observations->count; b++) {
        const ObservationBundle *bundle = &observations->bundles[b];
        const Instrument *inst = find_instrument(catalog, bundle->instrument_id);
        if (!inst) continue;
        double fs = effective_rate(inst);

        for (size_t w = 0; w < bundle->window_count; w++) {
            const ObsWindow *win = &bundle->windows[w];
            Peak local[14];
            size_t local_count = 0;

            for (int k = 8; k <= (int)win->sample_count / 2; k++) {
                double alias = (double)k * fs / (double)win->sample_count;
                if (alias < 80.0) continue;
                double p = peak_power_at(win, inst, alias);
                if (local_count < 14) {
                    local[local_count++] = (Peak){bundle, win, inst, alias, p, 0.0};
                    qsort(local, local_count, sizeof(local[0]), cmp_peak_power);
                } else if (p > local[local_count - 1].power && peak_far_enough(local, 0, local_count, alias)) {
                    local[local_count - 1] = (Peak){bundle, win, inst, alias, p, 0.0};
                    qsort(local, local_count, sizeof(local[0]), cmp_peak_power);
                }
            }

            double first_t = corrected_time(win->time_s[0], inst);
            double last_t = corrected_time(win->time_s[win->present_count - 1], inst);
            for (size_t i = 0; i < local_count && *peak_count < MAX_PEAKS; i++) {
                local[i].alias_hz = refine_alias(win, inst, local[i].alias_hz);
                local[i].mid_s = 0.5 * (first_t + last_t);
                peaks[(*peak_count)++] = local[i];
            }
        }
    }
    return 0;
}

static size_t build_candidates(const Peak *peaks, size_t peak_count, Candidate *cands) {
    size_t n = 0;
    for (size_t i = 0; i < peak_count; i++) {
        double fs = effective_rate(peaks[i].instrument);
        double a = peaks[i].alias_hz;
        for (int m = 0; m <= 4; m++) {
            double c1 = (double)m * fs + a;
            double c2 = (double)m * fs - a;
            if (c1 >= 1000.0 && c1 <= 40000.0 && n < MAX_CANDIDATES) {
                cands[n++] = (Candidate){c1, peaks[i].power, (int)i};
            }
            if (c2 >= 1000.0 && c2 <= 40000.0 && n < MAX_CANDIDATES) {
                cands[n++] = (Candidate){c2, peaks[i].power, (int)i};
            }
        }
    }
    return n;
}

static int cmp_candidate_freq(const void *a, const void *b) {
    const Candidate *ca = (const Candidate *)a;
    const Candidate *cb = (const Candidate *)b;
    return (ca->f_hz > cb->f_hz) - (ca->f_hz < cb->f_hz);
}

static size_t cluster_candidates(Candidate *cands, size_t cand_count, Cluster *clusters) {
    qsort(cands, cand_count, sizeof(cands[0]), cmp_candidate_freq);
    size_t cluster_count = 0;
    for (size_t i = 0; i < cand_count;) {
        double sum_w = 0.0;
        double sum_f = 0.0;
        int support = 0;
        double start = cands[i].f_hz;
        size_t j = i;
        while (j < cand_count && cands[j].f_hz - start <= 80.0) {
            sum_w += cands[j].weight;
            sum_f += cands[j].weight * cands[j].f_hz;
            support++;
            j++;
        }
        if (support >= 8 && cluster_count < MAX_CLUSTERS) {
            clusters[cluster_count++] = (Cluster){sum_f / sum_w, sum_w, support, 0};
        }
        i = j;
    }
    return cluster_count;
}

static int is_calibration(const Catalog *catalog, double f_hz) {
    for (size_t i = 0; i < catalog->calibration_count; i++) {
        if (fabs(f_hz - catalog->calibrations[i].f0_hz) < 55.0) return 1;
    }
    return 0;
}

static double true_frequency_from_peak(const Peak *peak, double center) {
    double fs = effective_rate(peak->instrument);
    double a = peak->alias_hz;
    double best = 0.0;
    double best_err = 1e100;
    for (int m = 0; m <= 4; m++) {
        double c[2] = {(double)m * fs + a, (double)m * fs - a};
        for (int i = 0; i < 2; i++) {
            if (c[i] < 1000.0 || c[i] > 40000.0) continue;
            double err = fabs(c[i] - center);
            if (err < best_err) {
                best_err = err;
                best = c[i];
            }
        }
    }
    return best;
}

static void cluster_peak_stats(const Peak *peaks, size_t peak_count, const unsigned char *used, double center, int *support, double *weight) {
    *support = 0;
    *weight = 0.0;
    for (size_t i = 0; i < peak_count; i++) {
        if (used && used[i]) continue;
        double expected_alias = fold_alias(center, effective_rate(peaks[i].instrument));
        if (fabs(expected_alias - peaks[i].alias_hz) > 42.0) continue;
        double tf = true_frequency_from_peak(&peaks[i], center);
        if (tf == 0.0 || fabs(tf - center) > 90.0) continue;
        (*support)++;
        *weight += peaks[i].power;
    }
}

static int fit_event(const Catalog *catalog, const Peak *peaks, size_t peak_count, unsigned char *used, double center, RecoveredEvent *out) {
    double sw = 0.0, st = 0.0, sf = 0.0, stt = 0.0, stf = 0.0;
    double first = 1e100, last = -1e100, power = 0.0;
    int support = 0;

    for (size_t i = 0; i < peak_count; i++) {
        if (used && used[i]) continue;
        double expected_alias = fold_alias(center, effective_rate(peaks[i].instrument));
        if (fabs(expected_alias - peaks[i].alias_hz) > 42.0) continue;
        double tf = true_frequency_from_peak(&peaks[i], center);
        if (tf == 0.0 || fabs(tf - center) > 90.0) continue;
        const SurveyWindow *survey = find_survey_window(catalog, peaks[i].window->window_id);
        double t = peaks[i].mid_s;
        double w = fmax(1.0, peaks[i].power);
        sw += w;
        st += w * t;
        sf += w * tf;
        stt += w * t * t;
        stf += w * t * tf;
        power += peaks[i].power;
        support++;
        if (survey) {
            if (survey->start_s < first) first = survey->start_s;
            if (survey->end_s > last) last = survey->end_s;
        }
        if (used) used[i] = 1;
    }

    if (support < 6 || sw == 0.0) return -1;
    double denom = sw * stt - st * st;
    double chirp = 0.0;
    double intercept = sf / sw;
    if (fabs(denom) > 1e-9) {
        chirp = (sw * stf - st * sf) / denom;
        intercept = (sf - chirp * st) / sw;
    }

    double start = first + 0.08;
    double end = last + 0.12;
    double f0 = intercept + chirp * start;

    out->f0_hz = f0;
    out->chirp_hz_per_s = chirp;
    out->start_s = start;
    out->end_s = end;
    out->relative_power = power / (double)support;
    out->support = support;
    return 0;
}

static int cmp_event_freq(const void *a, const void *b) {
    const RecoveredEvent *ea = (const RecoveredEvent *)a;
    const RecoveredEvent *eb = (const RecoveredEvent *)b;
    return (ea->f0_hz > eb->f0_hz) - (ea->f0_hz < eb->f0_hz);
}

int recover_events(const Catalog *catalog, const ObservationSet *observations, RecoveryResult *out) {
    memset(out, 0, sizeof(*out));
    Peak *peaks = calloc(MAX_PEAKS, sizeof(*peaks));
    Candidate *cands = calloc(MAX_CANDIDATES, sizeof(*cands));
    Cluster *clusters = calloc(MAX_CLUSTERS, sizeof(*clusters));
    RecoveredEvent *events = calloc(8, sizeof(*events));
    unsigned char *used_peaks = calloc(MAX_PEAKS, sizeof(*used_peaks));
    if (!peaks || !cands || !clusters || !events || !used_peaks) goto fail;

    size_t peak_count = 0;
    if (collect_peaks(catalog, observations, peaks, &peak_count) != 0) goto fail;
    size_t cand_count = build_candidates(peaks, peak_count, cands);
    size_t cluster_count = cluster_candidates(cands, cand_count, clusters);

    size_t event_count = 0;
    for (int pass = 0; pass < 3; pass++) {
        double best_score = -1.0;
        size_t best = (size_t)-1;
        for (size_t i = 0; i < cluster_count; i++) {
            if (clusters[i].used || is_calibration(catalog, clusters[i].center)) continue;
            int support = 0;
            double weight = 0.0;
            cluster_peak_stats(peaks, peak_count, used_peaks, clusters[i].center, &support, &weight);
            if (support < 6) continue;
            double score = weight * (double)support;
            if (score > best_score) {
                best_score = score;
                best = i;
            }
        }
        if (best == (size_t)-1) break;
        clusters[best].used = 1;
        if (fit_event(catalog, peaks, peak_count, used_peaks, clusters[best].center, &events[event_count]) == 0) {
            snprintf(events[event_count].event_id, sizeof(events[event_count].event_id), "E%02d", (int)event_count + 1);
            event_count++;
        }
    }

    qsort(events, event_count, sizeof(events[0]), cmp_event_freq);
    for (size_t i = 0; i < event_count; i++) {
        snprintf(events[i].event_id, sizeof(events[i].event_id), "E%02d", (int)i + 1);
    }

    out->count = event_count;
    out->events = events;
    free(peaks);
    free(cands);
    free(clusters);
    free(used_peaks);
    return 0;

fail:
    free(peaks);
    free(cands);
    free(clusters);
    free(events);
    free(used_peaks);
    return -1;
}

void free_recovery_result(RecoveryResult *result) {
    free(result->events);
    memset(result, 0, sizeof(*result));
}
