#include "assignment.h"

#include <float.h>
#include <stdlib.h>
#include <string.h>

void assign_result_free(AssignResult *r) {
    free(r->peak_to_ion);
    r->peak_to_ion = NULL;
    r->matched = 0;
    r->total_cost = 0.0;
}

/* Nearest-ion assignment in peak_id order. */
int assign_peaks(const AssignEdge *edges, size_t n_edges, size_t n_peaks,
                 size_t n_ions, const char *const *peak_ids,
                 const char *const *ion_ids, AssignResult *out) {
    (void)peak_ids;
    (void)ion_ids;
    memset(out, 0, sizeof(*out));
    out->peak_to_ion = calloc(n_peaks ? n_peaks : 1, sizeof(int));
    if (!out->peak_to_ion) {
        return -1;
    }
    for (size_t i = 0; i < n_peaks; i++) {
        out->peak_to_ion[i] = -1;
    }

    int *ion_used = calloc(n_ions ? n_ions : 1, sizeof(int));
    if (!ion_used) {
        return -1;
    }

    for (size_t p = 0; p < n_peaks; p++) {
        int best_j = -1;
        double best_cost = DBL_MAX;
        for (size_t e = 0; e < n_edges; e++) {
            if ((size_t)edges[e].peak_index != p) {
                continue;
            }
            int j = edges[e].ion_index;
            if (j < 0 || (size_t)j >= n_ions || ion_used[j]) {
                continue;
            }
            if (edges[e].cost < best_cost) {
                best_cost = edges[e].cost;
                best_j = j;
            }
        }
        if (best_j >= 0) {
            out->peak_to_ion[p] = best_j;
            ion_used[best_j] = 1;
            out->matched++;
            out->total_cost += best_cost;
        }
    }
    free(ion_used);
    return 0;
}
