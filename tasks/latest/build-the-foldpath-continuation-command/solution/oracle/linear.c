#include "foldpath/linear.h"

#include <math.h>

fp_result fp_linear_solve(size_t dimension, double *matrix, double *right_hand_side)
{
    size_t column;

    if (dimension == 0 || dimension > FP_MAX_VECTOR || matrix == NULL || right_hand_side == NULL) {
        return FP_INVALID;
    }

    for (column = 0; column < dimension; ++column) {
        size_t pivot_row = column;
        double pivot_magnitude = fabs(matrix[column * dimension + column]);
        size_t row;

        if (!isfinite(pivot_magnitude)) {
            return FP_INVALID;
        }
        for (row = column + 1; row < dimension; ++row) {
            double magnitude = fabs(matrix[row * dimension + column]);

            if (!isfinite(magnitude)) {
                return FP_INVALID;
            }
            if (magnitude > pivot_magnitude) {
                pivot_magnitude = magnitude;
                pivot_row = row;
            }
        }
        if (pivot_magnitude == 0.0) {
            return FP_INVALID;
        }
        if (pivot_row != column) {
            size_t item;
            double temporary;

            for (item = column; item < dimension; ++item) {
                temporary = matrix[column * dimension + item];
                matrix[column * dimension + item] = matrix[pivot_row * dimension + item];
                matrix[pivot_row * dimension + item] = temporary;
            }
            temporary = right_hand_side[column];
            right_hand_side[column] = right_hand_side[pivot_row];
            right_hand_side[pivot_row] = temporary;
        }

        for (row = column + 1; row < dimension; ++row) {
            double factor = matrix[row * dimension + column] /
                            matrix[column * dimension + column];
            size_t item;

            if (!isfinite(factor)) {
                return FP_INVALID;
            }
            matrix[row * dimension + column] = 0.0;
            for (item = column + 1; item < dimension; ++item) {
                matrix[row * dimension + item] -=
                    factor * matrix[column * dimension + item];
                if (!isfinite(matrix[row * dimension + item])) {
                    return FP_INVALID;
                }
            }
            right_hand_side[row] -= factor * right_hand_side[column];
            if (!isfinite(right_hand_side[row])) {
                return FP_INVALID;
            }
        }
    }

    for (column = dimension; column-- > 0;) {
        double value = right_hand_side[column];
        size_t item;
        double pivot = matrix[column * dimension + column];

        if (pivot == 0.0 || !isfinite(pivot)) {
            return FP_INVALID;
        }
        for (item = column + 1; item < dimension; ++item) {
            value -= matrix[column * dimension + item] * right_hand_side[item];
        }
        value /= pivot;
        if (!isfinite(value)) {
            return FP_INVALID;
        }
        right_hand_side[column] = value;
    }
    return FP_OK;
}

double fp_dot(const double *left, const double *right, size_t length)
{
    double total = 0.0;
    size_t index;

    if (left == NULL || right == NULL) {
        return NAN;
    }
    for (index = 0; index < length; ++index) {
        total += left[index] * right[index];
    }
    return total;
}

double fp_norm(const double *values, size_t length)
{
    double total = 0.0;
    size_t index;

    if (values == NULL) {
        return NAN;
    }
    for (index = 0; index < length; ++index) {
        total = hypot(total, values[index]);
    }
    return total;
}

fp_result fp_normalize(double *values, size_t length)
{
    double norm;
    size_t index;

    if (values == NULL || length == 0) {
        return FP_INVALID;
    }
    norm = fp_norm(values, length);
    if (!isfinite(norm) || norm == 0.0) {
        return FP_INVALID;
    }
    for (index = 0; index < length; ++index) {
        values[index] /= norm;
        if (!isfinite(values[index])) {
            return FP_INVALID;
        }
    }
    return FP_OK;
}
