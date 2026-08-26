#ifndef FOLDPATH_MODEL_H
#define FOLDPATH_MODEL_H

#include "foldpath/types.h"

fp_result fp_model_evaluate(
    const fp_model *model,
    const double x[FP_MAX_DIM],
    double lambda,
    double residual[FP_MAX_DIM],
    double state_jacobian[FP_MAX_DIM * FP_MAX_DIM],
    double parameter_derivative[FP_MAX_DIM]
);

double fp_residual_inf(
    const fp_model *model,
    const double x[FP_MAX_DIM],
    double lambda
);

fp_result fp_initial_tangent(
    const fp_model *model,
    const fp_control *control,
    double tangent[FP_MAX_VECTOR],
    double *start_residual
);

#endif
