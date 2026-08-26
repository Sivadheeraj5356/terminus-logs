#include "foldpath/model.h"

#include "foldpath/linear.h"

#include <math.h>
#include <string.h>

static int active_values_finite(const fp_model *model, const double *x, double lambda)
{
    size_t index;

    if (!isfinite(lambda)) {
        return 0;
    }
    for (index = 0; index < model->dimension; ++index) {
        if (!isfinite(x[index])) {
            return 0;
        }
    }
    return 1;
}

fp_result fp_model_evaluate(
    const fp_model *model,
    const double x[FP_MAX_DIM],
    double lambda,
    double residual[FP_MAX_DIM],
    double state_jacobian[FP_MAX_DIM * FP_MAX_DIM],
    double parameter_derivative[FP_MAX_DIM]
)
{
    size_t dimension;
    size_t index;

    if (model == NULL || x == NULL || residual == NULL || state_jacobian == NULL ||
        parameter_derivative == NULL || model->dimension == 0 ||
        model->dimension > FP_MAX_DIM || !active_values_finite(model, x, lambda)) {
        return FP_INVALID;
    }
    dimension = model->dimension;
    memset(residual, 0, sizeof(double) * FP_MAX_DIM);
    memset(state_jacobian, 0, sizeof(double) * FP_MAX_DIM * FP_MAX_DIM);
    memset(parameter_derivative, 0, sizeof(double) * FP_MAX_DIM);

    switch (model->kind) {
    case FP_MODEL_CUBIC:
        if (dimension != 1) {
            return FP_INVALID;
        }
        residual[0] = x[0] * x[0] * x[0] - model->parameters.cubic.a * x[0] +
                      lambda - model->parameters.cubic.bias;
        state_jacobian[0] = 3.0 * x[0] * x[0] - model->parameters.cubic.a;
        parameter_derivative[0] = 1.0;
        break;

    case FP_MODEL_COUPLED:
        if (dimension != 2) {
            return FP_INVALID;
        }
        residual[0] = x[0] * x[0] * x[0] - model->parameters.coupled.a * x[0] +
                      lambda + model->parameters.coupled.coupling * x[1] -
                      model->parameters.coupled.bias1;
        residual[1] = x[1] - model->parameters.coupled.gain * x[0] * x[0] -
                      model->parameters.coupled.bias2;
        state_jacobian[0] = 3.0 * x[0] * x[0] - model->parameters.coupled.a;
        state_jacobian[1] = model->parameters.coupled.coupling;
        state_jacobian[2] = -2.0 * model->parameters.coupled.gain * x[0];
        state_jacobian[3] = 1.0;
        parameter_derivative[0] = 1.0;
        parameter_derivative[1] = 0.0;
        break;

    case FP_MODEL_BRATU: {
        double h;
        double laplace_scale;

        if (dimension < 2) {
            return FP_INVALID;
        }
        h = 1.0 / ((double)dimension + 1.0);
        laplace_scale = model->parameters.bratu.scale / (h * h);
        if (!isfinite(laplace_scale)) {
            return FP_INVALID;
        }
        for (index = 0; index < dimension; ++index) {
            double left = index == 0 ? 0.0 : x[index - 1];
            double right = index + 1 == dimension ? 0.0 : x[index + 1];
            double exponential = exp(x[index]);

            residual[index] = laplace_scale * (left - 2.0 * x[index] + right) +
                              lambda * exponential;
            state_jacobian[index * dimension + index] =
                -2.0 * laplace_scale + lambda * exponential;
            if (index > 0) {
                state_jacobian[index * dimension + index - 1] = laplace_scale;
            }
            if (index + 1 < dimension) {
                state_jacobian[index * dimension + index + 1] = laplace_scale;
            }
            parameter_derivative[index] = exponential;
        }
        break;
    }

    default:
        return FP_INVALID;
    }

    for (index = 0; index < dimension; ++index) {
        size_t column;

        if (!isfinite(residual[index]) || !isfinite(parameter_derivative[index])) {
            return FP_INVALID;
        }
        for (column = 0; column < dimension; ++column) {
            if (!isfinite(state_jacobian[index * dimension + column])) {
                return FP_INVALID;
            }
        }
    }
    return FP_OK;
}

double fp_residual_inf(const fp_model *model, const double x[FP_MAX_DIM], double lambda)
{
    double residual[FP_MAX_DIM];
    double jacobian[FP_MAX_DIM * FP_MAX_DIM];
    double derivative[FP_MAX_DIM];
    double maximum = 0.0;
    size_t index;

    if (fp_model_evaluate(model, x, lambda, residual, jacobian, derivative) != FP_OK) {
        return INFINITY;
    }
    for (index = 0; index < model->dimension; ++index) {
        double magnitude = fabs(residual[index]);

        if (magnitude > maximum) {
            maximum = magnitude;
        }
    }
    return maximum;
}

fp_result fp_initial_tangent(
    const fp_model *model,
    const fp_control *control,
    double tangent[FP_MAX_VECTOR],
    double *start_residual
)
{
    double residual[FP_MAX_DIM];
    double matrix[FP_MAX_DIM * FP_MAX_DIM];
    double derivative[FP_MAX_DIM];
    double right_hand_side[FP_MAX_DIM];
    double residual_norm = 0.0;
    double orientation_dot;
    size_t index;

    if (model == NULL || control == NULL || tangent == NULL || start_residual == NULL ||
        model->dimension == 0 || model->dimension > FP_MAX_DIM) {
        return FP_INVALID;
    }
    if (fp_model_evaluate(model, model->start_x, model->start_lambda, residual, matrix,
                          derivative) != FP_OK) {
        return FP_INVALID;
    }
    for (index = 0; index < model->dimension; ++index) {
        double magnitude = fabs(residual[index]);

        if (magnitude > residual_norm) {
            residual_norm = magnitude;
        }
        right_hand_side[index] = -derivative[index];
    }
    if (residual_norm > control->residual_tolerance ||
        fp_linear_solve(model->dimension, matrix, right_hand_side) != FP_OK) {
        return FP_INVALID;
    }
    memset(tangent, 0, sizeof(double) * FP_MAX_VECTOR);
    for (index = 0; index < model->dimension; ++index) {
        tangent[index] = right_hand_side[index];
    }
    tangent[model->dimension] = 1.0;
    if (fp_normalize(tangent, model->dimension + 1) != FP_OK) {
        return FP_INVALID;
    }
    orientation_dot = fp_dot(tangent, model->orientation, model->dimension + 1);
    if (!isfinite(orientation_dot) || fabs(orientation_dot) <= 1e-14) {
        return FP_INVALID;
    }
    if (orientation_dot < 0.0) {
        for (index = 0; index < model->dimension + 1; ++index) {
            tangent[index] = -tangent[index];
        }
    }
    *start_residual = residual_norm;
    return FP_OK;
}
