#ifndef TOFLAB_MARKDOWN_H
#define TOFLAB_MARKDOWN_H

#include "matrix.h"

#include <stddef.h>

typedef struct {
    char candidate_id[64];
    char candidate_key[320];
    char source_file[256];
    int rev;
    Vec3 theta;
    Mat3 cov;
    double gscale;
    char row_serial[512];
} LabCandidate;

typedef struct {
    LabCandidate *items;
    size_t count;
    size_t cap;
} LabCandidateList;

typedef struct {
    char candidate_key[320];
    char reason[32];
} RejectedCandidate;

typedef struct {
    RejectedCandidate *items;
    size_t count;
    size_t cap;
} RejectedList;

void lab_list_init(LabCandidateList *list);
void lab_list_free(LabCandidateList *list);
int lab_list_push(LabCandidateList *list, const LabCandidate *item);

void rejected_list_init(RejectedList *list);
void rejected_list_free(RejectedList *list);
int rejected_list_push(RejectedList *list, const char *key, const char *reason);

/* Parse all *.md under notes_dir recursively. Returns 0 on success.
 * rejected collects superseded / invalid_covariance rows discovered during parse. */
int parse_lab_notes(const char *notes_dir, LabCandidateList *out, RejectedList *rejected);

#endif
