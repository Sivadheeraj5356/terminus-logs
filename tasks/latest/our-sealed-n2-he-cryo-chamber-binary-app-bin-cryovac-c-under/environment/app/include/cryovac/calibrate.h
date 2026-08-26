#ifndef CRYOVAC_CALIBRATE_H
#define CRYOVAC_CALIBRATE_H

#include "cryovac/types.h"

int cv_load_cal_table(const char *path, CvCalTable *out);
int cv_resolve_sorption(const CvCalTable *table, double temp_k, int leg, int prev_cal_seq,
                        CvSorption *out, int *seq_out);
int cv_sticky_eligible(const CvCalTable *table, const CvCalRow *row, double temp_k, int leg,
                       int prev_cal_seq);
const CvCalRow *cv_find_seq(const CvCalTable *table, int seq);

#endif
