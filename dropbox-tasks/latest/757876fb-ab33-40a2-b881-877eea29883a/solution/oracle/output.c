#include "foldpath/output.h"

#include "foldpath/path.h"
#include "foldpath/state.h"

#include <math.h>
#include <stdio.h>

const char *fp_status_name(fp_status status)
{
    switch (status) {
    case FP_STATUS_PARTIAL:
        return "partial";
    case FP_STATUS_COMPLETE:
        return "complete";
    case FP_STATUS_STALLED:
        return "stalled";
    default:
        return NULL;
    }
}

const char *fp_fold_name(fp_fold fold)
{
    switch (fold) {
    case FP_FOLD_NONE:
        return "none";
    case FP_FOLD_MAX_LAMBDA:
        return "max_lambda";
    case FP_FOLD_MIN_LAMBDA:
        return "min_lambda";
    default:
        return NULL;
    }
}

static int write_number(FILE *stream, double value)
{
    if (!isfinite(value)) {
        return 0;
    }
    if (value == 0.0) {
        return fputc('0', stream) != EOF;
    }
    return fprintf(stream, "%.17g", value) >= 0;
}

static int write_number_array(FILE *stream, const double *values, size_t count)
{
    size_t index;

    if (fputc('[', stream) == EOF) {
        return 0;
    }
    for (index = 0; index < count; ++index) {
        if ((index != 0 && fputc(',', stream) == EOF) || !write_number(stream, values[index])) {
            return 0;
        }
    }
    return fputc(']', stream) != EOF;
}

static int write_point(FILE *stream, const fp_state *state, const fp_point *point)
{
    if (fprintf(stream, "{\"type\":\"point\",\"index\":%zu,\"arclength\":", point->index) < 0 ||
        !write_number(stream, point->arclength) ||
        fputs(",\"step_used\":", stream) == EOF || !write_number(stream, point->step_used) ||
        fputs(",\"lambda\":", stream) == EOF || !write_number(stream, point->lambda) ||
        fputs(",\"x\":", stream) == EOF ||
        !write_number_array(stream, point->x, state->dimension) ||
        fputs(",\"residual_inf\":", stream) == EOF ||
        !write_number(stream, point->residual_inf) ||
        fprintf(stream, ",\"newton_iterations\":%u,\"tangent\":", point->newton_iterations) < 0 ||
        !write_number_array(stream, point->tangent, state->dimension + 1) ||
        fprintf(stream, ",\"fold\":\"%s\"}\n", fp_fold_name(point->fold)) < 0) {
        return 0;
    }
    return 1;
}

static int write_summary(FILE *stream, const fp_state *state)
{
    const fp_point *last = &state->points[state->point_count - 1];

    if (fprintf(stream,
                "{\"type\":\"summary\",\"status\":\"%s\",\"dimension\":%zu,"
                "\"points\":%zu,\"folds\":%zu,\"arclength\":",
                fp_status_name(state->status), state->dimension, state->point_count,
                state->fold_count) < 0 ||
        !write_number(stream, last->arclength) || fputs(",\"next_step\":", stream) == EOF ||
        !write_number(stream, state->next_step) || fputs("}\n", stream) == EOF) {
        return 0;
    }
    return 1;
}

fp_result fp_output_write_atomic(const char *path, const fp_state *state)
{
    fp_atomic_file file;
    fp_result result;
    size_t index;

    if (path == NULL || fp_state_validate(state) != FP_OK) {
        return FP_INVALID;
    }
    result = fp_atomic_begin(path, "w", &file);
    if (result != FP_OK) {
        return result;
    }
    for (index = 0; index < state->point_count; ++index) {
        if (!write_point(file.stream, state, &state->points[index])) {
            fp_atomic_abort(&file);
            return FP_IO;
        }
    }
    if (!write_summary(file.stream, state)) {
        fp_atomic_abort(&file);
        return FP_IO;
    }
    return fp_atomic_commit(&file);
}
