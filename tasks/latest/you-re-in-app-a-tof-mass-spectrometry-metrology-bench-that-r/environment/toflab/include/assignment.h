#ifndef TOFLAB_ASSIGNMENT_H
#define TOFLAB_ASSIGNMENT_H

#include <stddef.h>

typedef struct {
    int peak_index;
    int ion_index;
    double cost;
} AssignEdge;

typedef struct {
    int *peak_to_ion; /* length n_peaks, -1 if unmatched */
    double total_cost;
    int matched;
} AssignResult;

/* Exact max-cardinality min-cost assignment with deterministic tie-break.
 * peak_ids and ion_ids are used only for lexicographic tie resolution.
 * Returns 0 on success. */
int assign_peaks(const AssignEdge *edges, size_t n_edges,
                 size_t n_peaks, size_t n_ions,
                 const char *const *peak_ids, const char *const *ion_ids,
                 AssignResult *out);

void assign_result_free(AssignResult *r);

#endif
