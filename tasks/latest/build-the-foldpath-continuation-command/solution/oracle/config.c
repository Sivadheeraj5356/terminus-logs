#define _POSIX_C_SOURCE 200809L

#include "foldpath/config.h"

#include "foldpath/linear.h"

#include <ctype.h>
#include <errno.h>
#include <limits.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define FP_MAX_CONFIG_KEYS 32u
#define FP_FNV_OFFSET UINT64_C(14695981039346656037)
#define FP_FNV_PRIME UINT64_C(1099511628211)

typedef struct {
    char *key;
    char *value;
} config_entry;

typedef struct {
    config_entry entries[FP_MAX_CONFIG_KEYS];
    size_t count;
    uint64_t fingerprint;
} config_file;

static uint64_t hash_update(uint64_t hash, const unsigned char *bytes, size_t count)
{
    size_t index;

    for (index = 0; index < count; ++index) {
        hash ^= (uint64_t)bytes[index];
        hash *= FP_FNV_PRIME;
    }
    return hash;
}

static char *trim_ascii(char *text)
{
    char *end;

    while (*text == ' ' || *text == '\t') {
        ++text;
    }
    end = text + strlen(text);
    while (end > text && (end[-1] == ' ' || end[-1] == '\t')) {
        --end;
    }
    *end = '\0';
    return text;
}

static void config_free(config_file *config)
{
    size_t index;

    for (index = 0; index < config->count; ++index) {
        free(config->entries[index].key);
        free(config->entries[index].value);
    }
    memset(config, 0, sizeof(*config));
}

static int config_has_key(const config_file *config, const char *key)
{
    size_t index;

    for (index = 0; index < config->count; ++index) {
        if (strcmp(config->entries[index].key, key) == 0) {
            return 1;
        }
    }
    return 0;
}

static const char *config_value(const config_file *config, const char *key)
{
    size_t index;

    for (index = 0; index < config->count; ++index) {
        if (strcmp(config->entries[index].key, key) == 0) {
            return config->entries[index].value;
        }
    }
    return NULL;
}

static fp_result config_load(const char *path, config_file *config)
{
    char *line = NULL;
    size_t capacity = 0;
    FILE *stream;
    fp_result result = FP_OK;

    if (path == NULL || config == NULL) {
        return FP_INVALID;
    }
    memset(config, 0, sizeof(*config));
    config->fingerprint = FP_FNV_OFFSET;
    stream = fopen(path, "rb");
    if (stream == NULL) {
        return FP_IO;
    }

    for (;;) {
        ssize_t count = getline(&line, &capacity, stream);
        char *content;
        char *separator;
        char *key;
        char *value;
        size_t index;

        if (count < 0) {
            break;
        }
        config->fingerprint = hash_update(
            config->fingerprint,
            (const unsigned char *)line,
            (size_t)count
        );
        if (memchr(line, '\0', (size_t)count) != NULL) {
            result = FP_INVALID;
            break;
        }
        if (count > 0 && line[count - 1] == '\n') {
            line[count - 1] = '\0';
        }
        content = trim_ascii(line);
        if (*content == '\0' || *content == '#') {
            continue;
        }
        separator = strchr(content, '=');
        if (separator == NULL) {
            result = FP_INVALID;
            break;
        }
        *separator = '\0';
        key = trim_ascii(content);
        value = trim_ascii(separator + 1);
        if (*key == '\0' || config->count == FP_MAX_CONFIG_KEYS || config_has_key(config, key)) {
            result = FP_INVALID;
            break;
        }
        index = config->count;
        config->entries[index].key = strdup(key);
        config->entries[index].value = strdup(value);
        if (config->entries[index].key == NULL || config->entries[index].value == NULL) {
            free(config->entries[index].key);
            free(config->entries[index].value);
            config->entries[index].key = NULL;
            config->entries[index].value = NULL;
            result = FP_IO;
            break;
        }
        ++config->count;
    }
    if (result == FP_OK && ferror(stream)) {
        result = FP_IO;
    }
    free(line);
    if (fclose(stream) != 0 && result == FP_OK) {
        result = FP_IO;
    }
    if (result != FP_OK) {
        config_free(config);
    }
    return result;
}

static int decimal_float_syntax(const char *text)
{
    const unsigned char *cursor = (const unsigned char *)text;
    size_t before = 0;
    size_t after = 0;

    if (*cursor == '+' || *cursor == '-') {
        ++cursor;
    }
    while (isdigit(*cursor)) {
        ++before;
        ++cursor;
    }
    if (*cursor == '.') {
        ++cursor;
        while (isdigit(*cursor)) {
            ++after;
            ++cursor;
        }
    }
    if (before + after == 0) {
        return 0;
    }
    if (*cursor == 'e' || *cursor == 'E') {
        size_t exponent_digits = 0;

        ++cursor;
        if (*cursor == '+' || *cursor == '-') {
            ++cursor;
        }
        while (isdigit(*cursor)) {
            ++exponent_digits;
            ++cursor;
        }
        if (exponent_digits == 0) {
            return 0;
        }
    }
    return *cursor == '\0';
}

static int parse_double_value(const char *text, double *value)
{
    char *end = NULL;
    double parsed;

    if (text == NULL || value == NULL || !decimal_float_syntax(text)) {
        return 0;
    }
    errno = 0;
    parsed = strtod(text, &end);
    if (end == text || *end != '\0' || !isfinite(parsed)) {
        return 0;
    }
    *value = parsed;
    return 1;
}

static int parse_size_value(const char *text, size_t *value)
{
    const unsigned char *cursor = (const unsigned char *)text;
    size_t parsed = 0;

    if (text == NULL || value == NULL || *cursor == '\0') {
        return 0;
    }
    while (*cursor != '\0') {
        unsigned digit;

        if (!isdigit(*cursor)) {
            return 0;
        }
        digit = (unsigned)(*cursor - '0');
        if (parsed > (SIZE_MAX - digit) / 10u) {
            return 0;
        }
        parsed = parsed * 10u + digit;
        ++cursor;
    }
    *value = parsed;
    return 1;
}

static int parse_unsigned_value(const char *text, unsigned *value)
{
    size_t parsed;

    if (!parse_size_value(text, &parsed) || parsed > UINT_MAX) {
        return 0;
    }
    *value = (unsigned)parsed;
    return 1;
}

static int parse_vector(const char *text, size_t expected, double *values)
{
    char *copy;
    char *cursor;
    size_t count = 0;
    int valid = 1;

    if (text == NULL || values == NULL || expected == 0) {
        return 0;
    }
    copy = strdup(text);
    if (copy == NULL) {
        return 0;
    }
    cursor = copy;
    while (valid) {
        char *comma = strchr(cursor, ',');
        char *item;

        if (comma != NULL) {
            *comma = '\0';
        }
        item = trim_ascii(cursor);
        if (count >= expected || !parse_double_value(item, &values[count])) {
            valid = 0;
            break;
        }
        ++count;
        if (comma == NULL) {
            break;
        }
        cursor = comma + 1;
    }
    free(copy);
    return valid && count == expected;
}

static int key_allowed(const char *key, const char *const *allowed, size_t count)
{
    size_t index;

    for (index = 0; index < count; ++index) {
        if (strcmp(key, allowed[index]) == 0) {
            return 1;
        }
    }
    return 0;
}

static int exact_keys(const config_file *config, const char *const *allowed, size_t count)
{
    size_t index;

    if (config->count != count) {
        return 0;
    }
    for (index = 0; index < config->count; ++index) {
        if (!key_allowed(config->entries[index].key, allowed, count)) {
            return 0;
        }
    }
    return 1;
}

const char *fp_model_kind_name(fp_model_kind kind)
{
    switch (kind) {
    case FP_MODEL_CUBIC:
        return "cubic";
    case FP_MODEL_COUPLED:
        return "coupled";
    case FP_MODEL_BRATU:
        return "bratu";
    default:
        return NULL;
    }
}

fp_result fp_model_load(const char *path, fp_model *model, uint64_t *fingerprint)
{
    static const char *const cubic_keys[] = {
        "kind", "dimension", "start_lambda", "start_x", "orientation", "a", "bias"
    };
    static const char *const coupled_keys[] = {
        "kind", "dimension", "start_lambda", "start_x", "orientation",
        "a", "coupling", "gain", "bias1", "bias2"
    };
    static const char *const bratu_keys[] = {
        "kind", "dimension", "start_lambda", "start_x", "orientation", "scale"
    };
    config_file config;
    const char *kind;
    fp_model parsed;
    fp_result result;

    if (model == NULL || fingerprint == NULL) {
        return FP_INVALID;
    }
    result = config_load(path, &config);
    if (result != FP_OK) {
        return result;
    }
    memset(&parsed, 0, sizeof(parsed));
    kind = config_value(&config, "kind");
    if (kind == NULL || !parse_size_value(config_value(&config, "dimension"), &parsed.dimension) ||
        parsed.dimension == 0 || parsed.dimension > FP_MAX_DIM ||
        !parse_double_value(config_value(&config, "start_lambda"), &parsed.start_lambda)) {
        result = FP_INVALID;
        goto finish;
    }
    if (strcmp(kind, "cubic") == 0) {
        parsed.kind = FP_MODEL_CUBIC;
        if (!exact_keys(&config, cubic_keys, sizeof(cubic_keys) / sizeof(cubic_keys[0])) ||
            parsed.dimension != 1 ||
            !parse_double_value(config_value(&config, "a"), &parsed.parameters.cubic.a) ||
            !parse_double_value(config_value(&config, "bias"), &parsed.parameters.cubic.bias)) {
            result = FP_INVALID;
            goto finish;
        }
    } else if (strcmp(kind, "coupled") == 0) {
        parsed.kind = FP_MODEL_COUPLED;
        if (!exact_keys(&config, coupled_keys, sizeof(coupled_keys) / sizeof(coupled_keys[0])) ||
            parsed.dimension != 2 ||
            !parse_double_value(config_value(&config, "a"), &parsed.parameters.coupled.a) ||
            !parse_double_value(config_value(&config, "coupling"), &parsed.parameters.coupled.coupling) ||
            !parse_double_value(config_value(&config, "gain"), &parsed.parameters.coupled.gain) ||
            !parse_double_value(config_value(&config, "bias1"), &parsed.parameters.coupled.bias1) ||
            !parse_double_value(config_value(&config, "bias2"), &parsed.parameters.coupled.bias2)) {
            result = FP_INVALID;
            goto finish;
        }
    } else if (strcmp(kind, "bratu") == 0) {
        parsed.kind = FP_MODEL_BRATU;
        if (!exact_keys(&config, bratu_keys, sizeof(bratu_keys) / sizeof(bratu_keys[0])) ||
            parsed.dimension < 2 ||
            !parse_double_value(config_value(&config, "scale"), &parsed.parameters.bratu.scale) ||
            parsed.parameters.bratu.scale <= 0.0) {
            result = FP_INVALID;
            goto finish;
        }
    } else {
        result = FP_INVALID;
        goto finish;
    }
    if (!parse_vector(config_value(&config, "start_x"), parsed.dimension, parsed.start_x) ||
        !parse_vector(config_value(&config, "orientation"), parsed.dimension + 1, parsed.orientation) ||
        !isfinite(fp_norm(parsed.orientation, parsed.dimension + 1)) ||
        fp_norm(parsed.orientation, parsed.dimension + 1) == 0.0) {
        result = FP_INVALID;
        goto finish;
    }
    *model = parsed;
    *fingerprint = config.fingerprint;

finish:
    config_free(&config);
    return result;
}

fp_result fp_control_load(const char *path, fp_control *control, uint64_t *fingerprint)
{
    static const char *const keys[] = {
        "initial_step", "min_step", "max_step", "grow_factor", "shrink_factor",
        "fast_iterations", "slow_iterations", "max_newton_iterations",
        "residual_tolerance", "correction_tolerance", "fold_tangent_tolerance",
        "max_points"
    };
    config_file config;
    fp_control parsed;
    fp_result result;

    if (control == NULL || fingerprint == NULL) {
        return FP_INVALID;
    }
    result = config_load(path, &config);
    if (result != FP_OK) {
        return result;
    }
    memset(&parsed, 0, sizeof(parsed));
    if (!exact_keys(&config, keys, sizeof(keys) / sizeof(keys[0])) ||
        !parse_double_value(config_value(&config, "initial_step"), &parsed.initial_step) ||
        !parse_double_value(config_value(&config, "min_step"), &parsed.min_step) ||
        !parse_double_value(config_value(&config, "max_step"), &parsed.max_step) ||
        !parse_double_value(config_value(&config, "grow_factor"), &parsed.grow_factor) ||
        !parse_double_value(config_value(&config, "shrink_factor"), &parsed.shrink_factor) ||
        !parse_unsigned_value(config_value(&config, "fast_iterations"), &parsed.fast_iterations) ||
        !parse_unsigned_value(config_value(&config, "slow_iterations"), &parsed.slow_iterations) ||
        !parse_unsigned_value(config_value(&config, "max_newton_iterations"),
                              &parsed.max_newton_iterations) ||
        !parse_double_value(config_value(&config, "residual_tolerance"),
                            &parsed.residual_tolerance) ||
        !parse_double_value(config_value(&config, "correction_tolerance"),
                            &parsed.correction_tolerance) ||
        !parse_double_value(config_value(&config, "fold_tangent_tolerance"),
                            &parsed.fold_tangent_tolerance) ||
        !parse_size_value(config_value(&config, "max_points"), &parsed.max_points) ||
        parsed.min_step < 1e-8 || parsed.min_step > parsed.initial_step ||
        parsed.initial_step > parsed.max_step || parsed.max_step > 10.0 ||
        parsed.max_step / parsed.min_step > 1e6 ||
        parsed.grow_factor < 1.01 || parsed.grow_factor > 4.0 ||
        parsed.shrink_factor < 0.1 || parsed.shrink_factor > 0.8 ||
        !(parsed.fast_iterations < parsed.slow_iterations &&
          parsed.slow_iterations <= parsed.max_newton_iterations &&
          parsed.max_newton_iterations <= 64) ||
        !(parsed.residual_tolerance > 0.0) || !(parsed.correction_tolerance > 0.0) ||
        !(parsed.fold_tangent_tolerance > 0.0) || parsed.max_points < 2 ||
        parsed.max_points > FP_MAX_POINTS) {
        result = FP_INVALID;
    } else {
        *control = parsed;
        *fingerprint = config.fingerprint;
    }
    config_free(&config);
    return result;
}
