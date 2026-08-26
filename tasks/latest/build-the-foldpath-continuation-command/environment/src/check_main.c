#include "foldpath/config.h"
#include "foldpath/model.h"
#include "foldpath/path.h"

#include <inttypes.h>
#include <locale.h>
#include <math.h>
#include <stdio.h>
#include <string.h>

static int report_error(const char *code, int exit_status)
{
    (void)fprintf(stderr, "{\"error\":\"%s\"}\n", code);
    return exit_status;
}

static int print_number(double value)
{
    if (!isfinite(value)) {
        return 0;
    }
    if (value == 0.0) {
        return fputc('0', stdout) != EOF;
    }
    return printf("%.17g", value) >= 0;
}

int main(int argc, char **argv)
{
    const char *model_path = NULL;
    const char *control_path = NULL;
    fp_model model;
    fp_control control;
    uint64_t model_fingerprint;
    uint64_t control_fingerprint;
    double tangent[FP_MAX_VECTOR];
    double start_residual;
    fp_result result;
    int index;
    size_t component;

    if (setlocale(LC_ALL, "C") == NULL) {
        return report_error("io_error", 4);
    }
    if (argc != 5) {
        return report_error("usage", 2);
    }
    for (index = 1; index < argc; index += 2) {
        if (strcmp(argv[index], "--model") == 0 && model_path == NULL) {
            model_path = argv[index + 1];
        } else if (strcmp(argv[index], "--control") == 0 && control_path == NULL) {
            control_path = argv[index + 1];
        } else {
            return report_error("usage", 2);
        }
    }
    if (!fp_path_is_absolute(model_path) || !fp_path_is_absolute(control_path)) {
        return report_error("usage", 2);
    }

    result = fp_model_load(model_path, &model, &model_fingerprint);
    if (result == FP_IO) {
        return report_error("io_error", 4);
    }
    if (result != FP_OK) {
        return report_error("model_invalid", 2);
    }
    result = fp_control_load(control_path, &control, &control_fingerprint);
    if (result == FP_IO) {
        return report_error("io_error", 4);
    }
    if (result != FP_OK) {
        return report_error("control_invalid", 2);
    }
    if (fp_initial_tangent(&model, &control, tangent, &start_residual) != FP_OK) {
        return report_error("model_invalid", 2);
    }

    if (printf("{\"valid\":true,\"kind\":\"%s\",\"dimension\":%zu,"
               "\"model_fingerprint\":\"%016" PRIx64 "\","
               "\"control_fingerprint\":\"%016" PRIx64 "\","
               "\"start_residual_inf\":",
               fp_model_kind_name(model.kind), model.dimension, model_fingerprint,
               control_fingerprint) < 0 ||
        !print_number(start_residual) || fputs(",\"initial_tangent\":[", stdout) == EOF) {
        return 4;
    }
    for (component = 0; component < model.dimension + 1; ++component) {
        if ((component != 0 && fputc(',', stdout) == EOF) || !print_number(tangent[component])) {
            return 4;
        }
    }
    if (printf("],\"max_points\":%zu}\n", control.max_points) < 0 || fflush(stdout) != 0) {
        return 4;
    }
    return 0;
}
