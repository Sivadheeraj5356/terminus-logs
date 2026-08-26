#include "assignment.h"

#include <float.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

void assign_result_free(AssignResult *r) {
    free(r->peak_to_ion);
    r->peak_to_ion = NULL;
    r->matched = 0;
    r->total_cost = 0.0;
}

static void build_signature(char *buf, size_t cap, const int *peak_to_ion,
                            size_t n_peaks, const char *const *peak_ids,
                            const char *const *ion_ids) {
    char *parts[16];
    size_t nparts = 0;
    char tmp[160];
    for (size_t p = 0; p < n_peaks; p++) {
        if (peak_to_ion[p] < 0) {
            continue;
        }
        snprintf(tmp, sizeof(tmp), "%s=%s", peak_ids[p], ion_ids[peak_to_ion[p]]);
        parts[nparts++] = strdup(tmp);
        if (nparts >= 16) {
            break;
        }
    }
    for (size_t i = 0; i + 1 < nparts; i++) {
        for (size_t j = i + 1; j < nparts; j++) {
            if (strcmp(parts[i], parts[j]) > 0) {
                char *t = parts[i];
                parts[i] = parts[j];
                parts[j] = t;
            }
        }
    }
    size_t off = 0;
    buf[0] = '\0';
    for (size_t i = 0; i < nparts; i++) {
        size_t n = strlen(parts[i]);
        if (off + n + 2 >= cap) {
            free(parts[i]);
            continue;
        }
        if (i) {
            buf[off++] = ';';
        }
        memcpy(buf + off, parts[i], n);
        off += n;
        buf[off] = '\0';
        free(parts[i]);
    }
}

int assign_peaks(const AssignEdge *edges, size_t n_edges, size_t n_peaks,
                 size_t n_ions, const char *const *peak_ids,
                 const char *const *ion_ids, AssignResult *out) {
    memset(out, 0, sizeof(*out));
    out->peak_to_ion = calloc(n_peaks ? n_peaks : 1, sizeof(int));
    if (!out->peak_to_ion) {
        return -1;
    }
    for (size_t i = 0; i < n_peaks; i++) {
        out->peak_to_ion[i] = -1;
    }
    if (n_peaks == 0) {
        return 0;
    }
    if (n_ions > 16) {
        return -1;
    }

    double *cost = calloc(n_peaks * (n_ions ? n_ions : 1), sizeof(double));
    unsigned char *ok = calloc(n_peaks * (n_ions ? n_ions : 1), 1);
    if (!cost || !ok) {
        free(cost);
        free(ok);
        return -1;
    }
    for (size_t i = 0; i < n_peaks * n_ions; i++) {
        cost[i] = DBL_MAX;
    }
    for (size_t e = 0; e < n_edges; e++) {
        size_t p = (size_t)edges[e].peak_index;
        size_t j = (size_t)edges[e].ion_index;
        if (p >= n_peaks || j >= n_ions) {
            continue;
        }
        size_t idx = p * n_ions + j;
        ok[idx] = 1;
        cost[idx] = edges[e].cost;
    }

    size_t nmasks = 1u << n_ions;
    /* For each peak step, store best (matched, cost) and reconstruction links. */
    int *best_matched = calloc((n_peaks + 1) * nmasks, sizeof(int));
    double *best_cost = calloc((n_peaks + 1) * nmasks, sizeof(double));
    unsigned char *valid = calloc((n_peaks + 1) * nmasks, 1);
    int *prev_mask = calloc((n_peaks + 1) * nmasks, sizeof(int));
    int *chosen_ion = calloc((n_peaks + 1) * nmasks, sizeof(int));
    if (!best_matched || !best_cost || !valid || !prev_mask || !chosen_ion) {
        free(cost);
        free(ok);
        free(best_matched);
        free(best_cost);
        free(valid);
        free(prev_mask);
        free(chosen_ion);
        return -1;
    }

#define IDX(p, m) ((size_t)(p) * nmasks + (size_t)(m))
    valid[IDX(0, 0)] = 1;
    best_matched[IDX(0, 0)] = 0;
    best_cost[IDX(0, 0)] = 0.0;
    prev_mask[IDX(0, 0)] = -1;
    chosen_ion[IDX(0, 0)] = -1;

    for (size_t p = 0; p < n_peaks; p++) {
        for (size_t mask = 0; mask < nmasks; mask++) {
            if (!valid[IDX(p, mask)]) {
                continue;
            }
            int bm = best_matched[IDX(p, mask)];
            double bc = best_cost[IDX(p, mask)];

            /* skip peak */
            size_t dst = IDX(p + 1, mask);
            if (!valid[dst] || bm > best_matched[dst] ||
                (bm == best_matched[dst] && bc < best_cost[dst])) {
                valid[dst] = 1;
                best_matched[dst] = bm;
                best_cost[dst] = bc;
                prev_mask[dst] = (int)mask;
                chosen_ion[dst] = -1;
            }

            for (size_t j = 0; j < n_ions; j++) {
                if (mask & (1u << j)) {
                    continue;
                }
                size_t eidx = p * n_ions + j;
                if (!ok[eidx]) {
                    continue;
                }
                size_t nmask = mask | (1u << j);
                int nm = bm + 1;
                double nc = bc + cost[eidx];
                dst = IDX(p + 1, nmask);
                if (!valid[dst] || nm > best_matched[dst] ||
                    (nm == best_matched[dst] && nc < best_cost[dst])) {
                    valid[dst] = 1;
                    best_matched[dst] = nm;
                    best_cost[dst] = nc;
                    prev_mask[dst] = (int)mask;
                    chosen_ion[dst] = (int)j;
                }
            }
        }
    }

    int *map = calloc(n_peaks, sizeof(int));
    char best_sig[4096] = "";
    int have = 0;
    int best_m = -1;
    double best_c = DBL_MAX;
    size_t best_mask = 0;

    for (size_t mask = 0; mask < nmasks; mask++) {
        size_t idx = IDX(n_peaks, mask);
        if (!valid[idx]) {
            continue;
        }
        size_t m = mask;
        for (size_t p = n_peaks; p-- > 0;) {
            size_t id = IDX(p + 1, m);
            map[p] = chosen_ion[id];
            m = (size_t)prev_mask[id];
        }
        char sig[4096];
        build_signature(sig, sizeof(sig), map, n_peaks, peak_ids, ion_ids);
        int bm = best_matched[idx];
        double bc = best_cost[idx];
        int better = 0;
        if (!have || bm > best_m) {
            better = 1;
        } else if (bm == best_m) {
            if (bc < best_c - 1e-15) {
                better = 1;
            } else if (fabs(bc - best_c) <= 1e-15 &&
                       (best_sig[0] == '\0' || strcmp(sig, best_sig) < 0)) {
                better = 1;
            }
        }
        if (better) {
            have = 1;
            best_m = bm;
            best_c = bc;
            best_mask = mask;
            memcpy(best_sig, sig, sizeof(best_sig));
            memcpy(out->peak_to_ion, map, n_peaks * sizeof(int));
        }
    }
    free(map);

    if (have) {
        out->matched = best_m;
        out->total_cost = best_c;
        (void)best_mask;
    }

    free(cost);
    free(ok);
    free(best_matched);
    free(best_cost);
    free(valid);
    free(prev_mask);
    free(chosen_ion);
#undef IDX
    return 0;
}
