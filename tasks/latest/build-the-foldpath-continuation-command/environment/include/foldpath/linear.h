#ifndef FOLDPATH_LINEAR_H
#define FOLDPATH_LINEAR_H

#include "foldpath/types.h"

fp_result fp_linear_solve(size_t dimension, double *matrix, double *right_hand_side);
double fp_dot(const double *left, const double *right, size_t length);
double fp_norm(const double *values, size_t length);
fp_result fp_normalize(double *values, size_t length);

#endif
