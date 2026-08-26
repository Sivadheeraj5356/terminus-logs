#!/bin/bash
set -euo pipefail

export LANG=C
export LC_ALL=C
cd /opt/foldpath

# Restore the oracle implementations of the deliberately skeletal toolkit
# modules before adding the continuation engine.
install -m 0644 /solution/oracle/config.c src/config.c
install -m 0644 /solution/oracle/fingerprint.c src/fingerprint.c
install -m 0644 /solution/oracle/linear.c src/linear.c
install -m 0644 /solution/oracle/model.c src/model.c
install -m 0644 /solution/oracle/state.c src/state.c
install -m 0644 /solution/oracle/output.c src/output.c
install -m 0644 /solution/oracle/path.c src/path.c

cat > "src/foldpath_continuation.h" <<'FOLDPATH_SOURCE_0'
#ifndef FOLDPATH_CONTINUATION_H
#define FOLDPATH_CONTINUATION_H

#include "foldpath/types.h"

typedef enum {
    FP_ADVANCE_OK = 0,
    FP_ADVANCE_STALLED = 1,
    FP_ADVANCE_IO = 2
} fp_advance_result;

fp_advance_result fp_advance(
    const fp_model *model,
    const fp_control *control,
    fp_state *state,
    const char *checkpoint_path,
    int has_accept_limit,
    size_t accept_limit
);

#endif
FOLDPATH_SOURCE_0

cat > "src/foldpath_continuation.c" <<'FOLDPATH_SOURCE_1'
#include "foldpath_continuation.h"

#include "foldpath/linear.h"
#include "foldpath/model.h"
#include "foldpath/state.h"

#include <math.h>
#include <string.h>

static int tangent_sign(double value, double tolerance)
{
    if (value > tolerance) {
        return 1;
    }
    if (value < -tolerance) {
        return -1;
    }
    return 0;
}

static fp_result corrected_tangent(
    const fp_model *model,
    const double x[FP_MAX_DIM],
    double lambda,
    const double previous[FP_MAX_VECTOR],
    double tangent[FP_MAX_VECTOR]
)
{
    const size_t n = model->dimension;
    const size_t width = n + 1u;
    double residual[FP_MAX_DIM];
    double jacobian[FP_MAX_DIM * FP_MAX_DIM];
    double parameter[FP_MAX_DIM];
    double matrix[FP_MAX_VECTOR * FP_MAX_VECTOR] = {0};
    double right[FP_MAX_VECTOR] = {0};
    size_t row;
    size_t column;

    if (fp_model_evaluate(model, x, lambda, residual, jacobian, parameter) != FP_OK) {
        return FP_INVALID;
    }
    for (row = 0; row < n; ++row) {
        for (column = 0; column < n; ++column) {
            matrix[row * width + column] = jacobian[row * n + column];
        }
        matrix[row * width + n] = parameter[row];
    }
    for (column = 0; column < width; ++column) {
        matrix[n * width + column] = previous[column];
    }
    right[n] = 1.0;
    if (fp_linear_solve(width, matrix, right) != FP_OK ||
        fp_normalize(right, width) != FP_OK) {
        return FP_INVALID;
    }
    if (fp_dot(right, previous, width) < 0.0) {
        for (column = 0; column < width; ++column) {
            right[column] = -right[column];
        }
    }
    memcpy(tangent, right, width * sizeof(double));
    return FP_OK;
}

static fp_result attempt_step(
    const fp_model *model,
    const fp_control *control,
    const fp_point *previous,
    double step,
    fp_point *candidate
)
{
    const size_t n = model->dimension;
    const size_t width = n + 1u;
    double predictor[FP_MAX_VECTOR] = {0};
    double corrected[FP_MAX_VECTOR] = {0};
    double residual[FP_MAX_DIM];
    double jacobian[FP_MAX_DIM * FP_MAX_DIM];
    double parameter[FP_MAX_DIM];
    unsigned iterations = 0;
    size_t index;

    for (index = 0; index < n; ++index) {
        predictor[index] = previous->x[index] + step * previous->tangent[index];
    }
    predictor[n] = previous->lambda + step * previous->tangent[n];
    memcpy(corrected, predictor, width * sizeof(double));
    for (index = 0; index < width; ++index) {
        if (!isfinite(corrected[index])) {
            return FP_INVALID;
        }
    }

    for (;;) {
        double plane = 0.0;
        double residual_inf = 0.0;
        size_t row;
        size_t column;

        if (fp_model_evaluate(
                model,
                corrected,
                corrected[n],
                residual,
                jacobian,
                parameter
            ) != FP_OK) {
            return FP_INVALID;
        }
        for (row = 0; row < n; ++row) {
            double magnitude = fabs(residual[row]);
            if (magnitude > residual_inf) {
                residual_inf = magnitude;
            }
        }
        for (column = 0; column < width; ++column) {
            plane += previous->tangent[column] * (corrected[column] - predictor[column]);
        }
        if (residual_inf <= control->residual_tolerance &&
            fabs(plane) <= control->correction_tolerance) {
            double next_tangent[FP_MAX_VECTOR];
            double displacement[FP_MAX_VECTOR];

            if (corrected_tangent(
                    model,
                    corrected,
                    corrected[n],
                    previous->tangent,
                    next_tangent
                ) != FP_OK) {
                return FP_INVALID;
            }
            memset(candidate, 0, sizeof(*candidate));
            candidate->index = previous->index + 1u;
            candidate->step_used = step;
            candidate->lambda = corrected[n];
            candidate->residual_inf = residual_inf;
            candidate->newton_iterations = iterations;
            candidate->fold = FP_FOLD_NONE;
            memcpy(candidate->x, corrected, n * sizeof(double));
            memcpy(candidate->tangent, next_tangent, width * sizeof(double));
            for (column = 0; column < width; ++column) {
                double old_value = column < n ? previous->x[column] : previous->lambda;
                displacement[column] = corrected[column] - old_value;
            }
            candidate->arclength = previous->arclength + fp_norm(displacement, width);
            if (!isfinite(candidate->arclength)) {
                return FP_INVALID;
            }
            return FP_OK;
        }
        if (iterations == control->max_newton_iterations) {
            return FP_INVALID;
        }
        {
            double matrix[FP_MAX_VECTOR * FP_MAX_VECTOR] = {0};
            double right[FP_MAX_VECTOR] = {0};

            for (row = 0; row < n; ++row) {
                for (column = 0; column < n; ++column) {
                    matrix[row * width + column] = jacobian[row * n + column];
                }
                matrix[row * width + n] = parameter[row];
                right[row] = -residual[row];
            }
            for (column = 0; column < width; ++column) {
                matrix[n * width + column] = previous->tangent[column];
            }
            right[n] = -plane;
            if (fp_linear_solve(width, matrix, right) != FP_OK) {
                return FP_INVALID;
            }
            for (column = 0; column < width; ++column) {
                corrected[column] += right[column];
                if (!isfinite(corrected[column])) {
                    return FP_INVALID;
                }
            }
        }
        ++iterations;
    }
}

static void classify_fold(
    const fp_control *control,
    fp_state *state,
    fp_point *candidate
)
{
    int sign = tangent_sign(
        candidate->tangent[state->dimension],
        control->fold_tangent_tolerance
    );

    candidate->fold = FP_FOLD_NONE;
    if (sign == 0) {
        return;
    }
    if (state->retained_fold_sign != 0 && sign != state->retained_fold_sign) {
        if (state->retained_fold_sign > 0 && sign < 0) {
            candidate->fold = FP_FOLD_MAX_LAMBDA;
        } else {
            candidate->fold = FP_FOLD_MIN_LAMBDA;
        }
        ++state->fold_count;
    }
    state->retained_fold_sign = sign;
}

static double adapted_step(const fp_control *control, const fp_point *point)
{
    double next = point->step_used;

    if (point->newton_iterations <= control->fast_iterations) {
        next = point->step_used * control->grow_factor;
        if (next > control->max_step) {
            next = control->max_step;
        }
    } else if (point->newton_iterations >= control->slow_iterations) {
        next = point->step_used * control->shrink_factor;
        if (next < control->min_step) {
            next = control->min_step;
        }
    }
    return next;
}

fp_advance_result fp_advance(
    const fp_model *model,
    const fp_control *control,
    fp_state *state,
    const char *checkpoint_path,
    int has_accept_limit,
    size_t accept_limit
)
{
    size_t accepted_here = 0;

    if (state->point_count >= control->max_points) {
        state->status = FP_STATUS_COMPLETE;
        return fp_state_write_atomic(checkpoint_path, state) == FP_OK
                   ? FP_ADVANCE_OK
                   : FP_ADVANCE_IO;
    }
    state->status = FP_STATUS_PARTIAL;
    while (state->point_count < control->max_points &&
           (!has_accept_limit || accepted_here < accept_limit)) {
        double step = state->next_step;

        for (;;) {
            fp_point candidate;

            if (attempt_step(
                    model,
                    control,
                    &state->points[state->point_count - 1u],
                    step,
                    &candidate
                ) == FP_OK) {
                classify_fold(control, state, &candidate);
                state->points[state->point_count] = candidate;
                ++state->point_count;
                ++accepted_here;
                state->next_step = adapted_step(control, &candidate);
                state->status = state->point_count == control->max_points
                                    ? FP_STATUS_COMPLETE
                                    : FP_STATUS_PARTIAL;
                if (fp_state_write_atomic(checkpoint_path, state) != FP_OK) {
                    return FP_ADVANCE_IO;
                }
                break;
            }
            if (step == control->min_step) {
                state->next_step = control->min_step;
                state->status = FP_STATUS_STALLED;
                if (fp_state_write_atomic(checkpoint_path, state) != FP_OK) {
                    return FP_ADVANCE_IO;
                }
                return FP_ADVANCE_STALLED;
            }
            step *= control->shrink_factor;
            if (step < control->min_step) {
                step = control->min_step;
            }
        }
    }
    return FP_ADVANCE_OK;
}
FOLDPATH_SOURCE_1

cat > "src/foldpath_main.c" <<'FOLDPATH_SOURCE_2'
#include "foldpath_continuation.h"

#include "foldpath/config.h"
#include "foldpath/model.h"
#include "foldpath/output.h"
#include "foldpath/path.h"
#include "foldpath/state.h"

#include <errno.h>
#include <limits.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct {
    int resume;
    const char *model_path;
    const char *control_path;
    const char *output_path;
    const char *checkpoint_path;
    int has_accept_limit;
    size_t accept_limit;
} options;

static int emit_error(const char *code, int exit_code)
{
    (void)fprintf(stderr, "{\"error\":\"%s\"}\n", code);
    return exit_code;
}

static int parse_positive_size(const char *text, size_t *value)
{
    size_t parsed = 0;
    const unsigned char *cursor = (const unsigned char *)text;

    if (text == NULL || *cursor == '\0') {
        return 0;
    }
    while (*cursor != '\0') {
        unsigned digit;
        if (*cursor < '0' || *cursor > '9') {
            return 0;
        }
        digit = (unsigned)(*cursor - '0');
        if (parsed > (SIZE_MAX - digit) / 10u) {
            return 0;
        }
        parsed = parsed * 10u + digit;
        ++cursor;
    }
    if (parsed == 0) {
        return 0;
    }
    *value = parsed;
    return 1;
}

static int parse_options(int argc, char **argv, options *parsed)
{
    int index;

    memset(parsed, 0, sizeof(*parsed));
    if (argc < 2) {
        return 0;
    }
    if (strcmp(argv[1], "run") == 0) {
        parsed->resume = 0;
    } else if (strcmp(argv[1], "resume") == 0) {
        parsed->resume = 1;
    } else {
        return 0;
    }
    if ((argc - 2) % 2 != 0) {
        return 0;
    }
    for (index = 2; index < argc; index += 2) {
        const char *key = argv[index];
        const char *value = argv[index + 1];

        if (strcmp(key, "--model") == 0 && parsed->model_path == NULL) {
            parsed->model_path = value;
        } else if (strcmp(key, "--control") == 0 && parsed->control_path == NULL) {
            parsed->control_path = value;
        } else if (strcmp(key, "--output") == 0 && parsed->output_path == NULL) {
            parsed->output_path = value;
        } else if (strcmp(key, "--checkpoint") == 0 && parsed->checkpoint_path == NULL) {
            parsed->checkpoint_path = value;
        } else if (strcmp(key, "--accept-limit") == 0 && !parsed->has_accept_limit) {
            if (!parse_positive_size(value, &parsed->accept_limit)) {
                return 0;
            }
            parsed->has_accept_limit = 1;
        } else {
            return 0;
        }
    }
    if (parsed->model_path == NULL || parsed->control_path == NULL ||
        parsed->output_path == NULL || parsed->checkpoint_path == NULL) {
        return 0;
    }
    if (!fp_path_is_absolute(parsed->model_path) ||
        !fp_path_is_absolute(parsed->control_path) ||
        !fp_path_is_absolute(parsed->output_path) ||
        !fp_path_is_absolute(parsed->checkpoint_path)) {
        return 0;
    }
    return 1;
}

static int has_path_conflict(const options *parsed)
{
    const char *paths[4] = {
        parsed->model_path,
        parsed->control_path,
        parsed->output_path,
        parsed->checkpoint_path
    };
    size_t left;
    size_t right;

    for (left = 0; left < 4; ++left) {
        for (right = left + 1; right < 4; ++right) {
            if (fp_paths_equal(paths[left], paths[right])) {
                return 1;
            }
        }
    }
    return 0;
}

static int load_model_and_control(
    const options *parsed,
    fp_model *model,
    fp_control *control,
    uint64_t *model_fingerprint,
    uint64_t *control_fingerprint,
    double initial_tangent[FP_MAX_VECTOR],
    double *initial_residual
)
{
    fp_result result;

    result = fp_model_load(parsed->model_path, model, model_fingerprint);
    if (result == FP_INVALID) {
        return emit_error("model_invalid", 2);
    }
    if (result != FP_OK) {
        return emit_error("io_error", 4);
    }
    result = fp_control_load(parsed->control_path, control, control_fingerprint);
    if (result == FP_INVALID) {
        return emit_error("control_invalid", 2);
    }
    if (result != FP_OK) {
        return emit_error("io_error", 4);
    }
    if (fp_initial_tangent(model, control, initial_tangent, initial_residual) != FP_OK) {
        return emit_error("model_invalid", 2);
    }
    return 0;
}

static int initial_sign(double value, double tolerance)
{
    if (value > tolerance) {
        return 1;
    }
    if (value < -tolerance) {
        return -1;
    }
    return 0;
}

int main(int argc, char **argv)
{
    options parsed;
    fp_model model;
    fp_control control;
    fp_state state;
    uint64_t model_fingerprint = 0;
    uint64_t control_fingerprint = 0;
    double initial_tangent[FP_MAX_VECTOR] = {0};
    double initial_residual = 0.0;
    int result;
    fp_advance_result advance_result;

    if (!parse_options(argc, argv, &parsed)) {
        return emit_error("usage", 2);
    }
    if (has_path_conflict(&parsed)) {
        return emit_error("path_conflict", 2);
    }
    result = load_model_and_control(
        &parsed,
        &model,
        &control,
        &model_fingerprint,
        &control_fingerprint,
        initial_tangent,
        &initial_residual
    );
    if (result != 0) {
        return result;
    }

    if (parsed.resume) {
        fp_result load_result = fp_state_load(parsed.checkpoint_path, &state);
        if (load_result == FP_MISSING) {
            return emit_error("state_missing", 2);
        }
        if (load_result == FP_INVALID) {
            return emit_error("state_invalid", 2);
        }
        if (load_result != FP_OK) {
            return emit_error("io_error", 4);
        }
        if (state.model_fingerprint != model_fingerprint ||
            state.control_fingerprint != control_fingerprint ||
            state.dimension != model.dimension) {
            return emit_error("state_mismatch", 2);
        }
    } else {
        fp_point *first;

        fp_state_init(&state, model.dimension, model_fingerprint, control_fingerprint);
        first = &state.points[0];
        first->index = 0;
        first->arclength = 0.0;
        first->step_used = 0.0;
        first->lambda = model.start_lambda;
        memcpy(first->x, model.start_x, model.dimension * sizeof(double));
        first->residual_inf = initial_residual;
        first->newton_iterations = 0;
        memcpy(first->tangent, initial_tangent, (model.dimension + 1u) * sizeof(double));
        first->fold = FP_FOLD_NONE;
        state.point_count = 1;
        state.next_step = control.initial_step;
        state.fold_count = 0;
        state.retained_fold_sign = initial_sign(
            initial_tangent[model.dimension],
            control.fold_tangent_tolerance
        );
        state.status = FP_STATUS_PARTIAL;
        if (fp_state_write_atomic(parsed.checkpoint_path, &state) != FP_OK) {
            return emit_error("io_error", 4);
        }
    }

    advance_result = fp_advance(
        &model,
        &control,
        &state,
        parsed.checkpoint_path,
        parsed.has_accept_limit,
        parsed.accept_limit
    );
    if (advance_result == FP_ADVANCE_IO) {
        return emit_error("io_error", 4);
    }
    if (fp_output_write_atomic(parsed.output_path, &state) != FP_OK) {
        return emit_error("io_error", 4);
    }
    return advance_result == FP_ADVANCE_STALLED ? 3 : 0;
}
FOLDPATH_SOURCE_2

make clean all install
