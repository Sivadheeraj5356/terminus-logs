#include "foldpath/linear.h"

/*
 * Deliberate task scaffold. Deterministic partial-pivot elimination, finite
 * checks, back-substitution, and stable vector helpers are part of the task.
 */

fp_result fp_linear_solve(size_t dimension, double *matrix, double *right_hand_side)
{
    (void)dimension;
    (void)matrix;
    (void)right_hand_side;
    return FP_INVALID;
}

double fp_dot(const double *left, const double *right, size_t length)
{
    (void)left;
    (void)right;
    (void)length;
    return 0.0;
}

double fp_norm(const double *values, size_t length)
{
    (void)values;
    (void)length;
    return 0.0;
}

fp_result fp_normalize(double *values, size_t length)
{
    (void)values;
    (void)length;
    return FP_INVALID;
}
