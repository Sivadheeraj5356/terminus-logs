#include "foldpath/model.h"

#include <math.h>

/*
 * Deliberate task scaffold. Equation evaluation, analytic Jacobians,
 * non-finite detection, residual measurement, and oriented initial tangents
 * must be implemented from the public mathematical contract.
 */

fp_result fp_model_evaluate(
    const fp_model *model,
    const double x[FP_MAX_DIM],
    double lambda,
    double residual[FP_MAX_DIM],
    double state_jacobian[FP_MAX_DIM * FP_MAX_DIM],
    double parameter_derivative[FP_MAX_DIM]
)
{
    (void)model;
    (void)x;
    (void)lambda;
    (void)residual;
    (void)state_jacobian;
    (void)parameter_derivative;
    return FP_INVALID;
}

double fp_residual_inf(
    const fp_model *model,
    const double x[FP_MAX_DIM],
    double lambda
)
{
    (void)model;
    (void)x;
    (void)lambda;
    return NAN;
}

fp_result fp_initial_tangent(
    const fp_model *model,
    const fp_control *control,
    double tangent[FP_MAX_VECTOR],
    double *start_residual
)
{
    (void)model;
    (void)control;
    (void)tangent;
    (void)start_residual;
    return FP_INVALID;
}
