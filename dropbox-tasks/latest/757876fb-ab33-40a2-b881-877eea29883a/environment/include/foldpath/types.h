#ifndef FOLDPATH_TYPES_H
#define FOLDPATH_TYPES_H

#include <stddef.h>
#include <stdint.h>

#define FP_MAX_DIM 8u
#define FP_MAX_VECTOR (FP_MAX_DIM + 1u)
#define FP_MAX_POINTS 512u

typedef enum {
    FP_OK = 0,
    FP_INVALID = 1,
    FP_IO = 2,
    FP_MISSING = 3
} fp_result;

typedef enum {
    FP_MODEL_CUBIC = 1,
    FP_MODEL_COUPLED = 2,
    FP_MODEL_BRATU = 3
} fp_model_kind;

typedef enum {
    FP_STATUS_PARTIAL = 1,
    FP_STATUS_COMPLETE = 2,
    FP_STATUS_STALLED = 3
} fp_status;

typedef enum {
    FP_FOLD_NONE = 0,
    FP_FOLD_MAX_LAMBDA = 1,
    FP_FOLD_MIN_LAMBDA = 2
} fp_fold;

typedef struct {
    fp_model_kind kind;
    size_t dimension;
    double start_lambda;
    double start_x[FP_MAX_DIM];
    double orientation[FP_MAX_VECTOR];
    union {
        struct {
            double a;
            double bias;
        } cubic;
        struct {
            double a;
            double coupling;
            double gain;
            double bias1;
            double bias2;
        } coupled;
        struct {
            double scale;
        } bratu;
    } parameters;
} fp_model;

typedef struct {
    double initial_step;
    double min_step;
    double max_step;
    double grow_factor;
    double shrink_factor;
    unsigned fast_iterations;
    unsigned slow_iterations;
    unsigned max_newton_iterations;
    double residual_tolerance;
    double correction_tolerance;
    double fold_tangent_tolerance;
    size_t max_points;
} fp_control;

typedef struct {
    size_t index;
    double arclength;
    double step_used;
    double lambda;
    double x[FP_MAX_DIM];
    double residual_inf;
    unsigned newton_iterations;
    double tangent[FP_MAX_VECTOR];
    fp_fold fold;
} fp_point;

typedef struct {
    uint64_t model_fingerprint;
    uint64_t control_fingerprint;
    size_t dimension;
    fp_status status;
    size_t point_count;
    fp_point points[FP_MAX_POINTS];
    double next_step;
    size_t fold_count;
    int retained_fold_sign;
} fp_state;

#endif
