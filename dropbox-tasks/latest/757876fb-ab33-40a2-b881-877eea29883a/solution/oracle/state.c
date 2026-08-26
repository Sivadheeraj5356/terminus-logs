#include "foldpath/state.h"

#include "foldpath/fingerprint.h"
#include "foldpath/linear.h"
#include "foldpath/path.h"

#include <errno.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define FP_STATE_VERSION UINT32_C(1)
#define FP_STATE_HEADER_SIZE 68u
#define FP_STATE_POINT_FIXED_SIZE 48u
#define FP_STATE_TRAILER_SIZE 8u
#define FP_STATE_MAX_SIZE \
    (FP_STATE_HEADER_SIZE + FP_MAX_POINTS * \
     (FP_STATE_POINT_FIXED_SIZE + (2u * FP_MAX_DIM + 1u) * 8u) + FP_STATE_TRAILER_SIZE)

static const unsigned char state_magic[8] = {'F', 'O', 'L', 'D', 'S', 'T', '0', '1'};

typedef struct {
    unsigned char *data;
    size_t size;
    size_t offset;
} byte_cursor;

static void put_u32(byte_cursor *cursor, uint32_t value)
{
    size_t index;

    for (index = 0; index < 4; ++index) {
        cursor->data[cursor->offset++] = (unsigned char)(value >> (8u * index));
    }
}

static void put_u64(byte_cursor *cursor, uint64_t value)
{
    size_t index;

    for (index = 0; index < 8; ++index) {
        cursor->data[cursor->offset++] = (unsigned char)(value >> (8u * index));
    }
}

static void put_double(byte_cursor *cursor, double value)
{
    uint64_t bits;

    memcpy(&bits, &value, sizeof(bits));
    put_u64(cursor, bits);
}

static int get_u32(byte_cursor *cursor, uint32_t *value)
{
    uint32_t parsed = 0;
    size_t index;

    if (cursor->offset > cursor->size || cursor->size - cursor->offset < 4) {
        return 0;
    }
    for (index = 0; index < 4; ++index) {
        parsed |= (uint32_t)cursor->data[cursor->offset++] << (8u * index);
    }
    *value = parsed;
    return 1;
}

static int get_u64(byte_cursor *cursor, uint64_t *value)
{
    uint64_t parsed = 0;
    size_t index;

    if (cursor->offset > cursor->size || cursor->size - cursor->offset < 8) {
        return 0;
    }
    for (index = 0; index < 8; ++index) {
        parsed |= (uint64_t)cursor->data[cursor->offset++] << (8u * index);
    }
    *value = parsed;
    return 1;
}

static int get_double(byte_cursor *cursor, double *value)
{
    uint64_t bits;

    if (!get_u64(cursor, &bits)) {
        return 0;
    }
    memcpy(value, &bits, sizeof(bits));
    return 1;
}

static size_t serialized_size(size_t dimension, size_t point_count)
{
    size_t point_size = FP_STATE_POINT_FIXED_SIZE + (2u * dimension + 1u) * 8u;

    return FP_STATE_HEADER_SIZE + point_count * point_size + FP_STATE_TRAILER_SIZE;
}

void fp_state_init(
    fp_state *state,
    size_t dimension,
    uint64_t model_fingerprint,
    uint64_t control_fingerprint
)
{
    if (state == NULL) {
        return;
    }
    memset(state, 0, sizeof(*state));
    state->dimension = dimension;
    state->model_fingerprint = model_fingerprint;
    state->control_fingerprint = control_fingerprint;
    state->status = FP_STATUS_PARTIAL;
}

fp_result fp_state_validate(const fp_state *state)
{
    size_t index;
    size_t counted_folds = 0;

    if (state == NULL || state->dimension == 0 || state->dimension > FP_MAX_DIM ||
        state->point_count == 0 || state->point_count > FP_MAX_POINTS ||
        (state->status != FP_STATUS_PARTIAL && state->status != FP_STATUS_COMPLETE &&
         state->status != FP_STATUS_STALLED) ||
        !isfinite(state->next_step) || state->next_step <= 0.0 ||
        (state->retained_fold_sign != -1 && state->retained_fold_sign != 0 &&
         state->retained_fold_sign != 1)) {
        return FP_INVALID;
    }
    for (index = 0; index < state->point_count; ++index) {
        const fp_point *point = &state->points[index];
        double tangent_norm;
        size_t component;

        if (point->index != index || !isfinite(point->arclength) || point->arclength < 0.0 ||
            !isfinite(point->step_used) || point->step_used < 0.0 ||
            !isfinite(point->lambda) || !isfinite(point->residual_inf) ||
            point->residual_inf < 0.0 ||
            (point->fold != FP_FOLD_NONE && point->fold != FP_FOLD_MAX_LAMBDA &&
             point->fold != FP_FOLD_MIN_LAMBDA)) {
            return FP_INVALID;
        }
        if (index == 0) {
            if (point->arclength != 0.0 || point->step_used != 0.0 ||
                point->newton_iterations != 0 || point->fold != FP_FOLD_NONE) {
                return FP_INVALID;
            }
        } else if (point->step_used <= 0.0 ||
                   point->arclength < state->points[index - 1].arclength) {
            return FP_INVALID;
        }
        for (component = 0; component < state->dimension; ++component) {
            if (!isfinite(point->x[component])) {
                return FP_INVALID;
            }
        }
        for (component = 0; component < state->dimension + 1; ++component) {
            if (!isfinite(point->tangent[component])) {
                return FP_INVALID;
            }
        }
        tangent_norm = fp_norm(point->tangent, state->dimension + 1);
        if (!isfinite(tangent_norm) || fabs(tangent_norm - 1.0) > 1e-10) {
            return FP_INVALID;
        }
        if (point->fold != FP_FOLD_NONE) {
            ++counted_folds;
        }
    }
    if (counted_folds != state->fold_count || state->fold_count > state->point_count) {
        return FP_INVALID;
    }
    return FP_OK;
}

static void serialize_state(const fp_state *state, unsigned char *buffer, size_t size)
{
    byte_cursor cursor = {buffer, size, 0};
    size_t index;

    memcpy(buffer, state_magic, sizeof(state_magic));
    cursor.offset += sizeof(state_magic);
    put_u32(&cursor, FP_STATE_VERSION);
    put_u32(&cursor, (uint32_t)state->dimension);
    put_u64(&cursor, state->model_fingerprint);
    put_u64(&cursor, state->control_fingerprint);
    put_u32(&cursor, (uint32_t)state->status);
    put_u32(&cursor, (uint32_t)state->point_count);
    put_u32(&cursor, (uint32_t)state->fold_count);
    put_u32(&cursor, (uint32_t)(int32_t)state->retained_fold_sign);
    put_double(&cursor, state->next_step);
    put_u64(&cursor, UINT64_C(0));
    put_u32(&cursor, UINT32_C(0));

    for (index = 0; index < state->point_count; ++index) {
        const fp_point *point = &state->points[index];
        size_t component;

        put_u32(&cursor, (uint32_t)point->index);
        put_u32(&cursor, point->newton_iterations);
        put_u32(&cursor, (uint32_t)point->fold);
        put_u32(&cursor, UINT32_C(0));
        put_double(&cursor, point->arclength);
        put_double(&cursor, point->step_used);
        put_double(&cursor, point->lambda);
        put_double(&cursor, point->residual_inf);
        for (component = 0; component < state->dimension; ++component) {
            put_double(&cursor, point->x[component]);
        }
        for (component = 0; component < state->dimension + 1; ++component) {
            put_double(&cursor, point->tangent[component]);
        }
    }
    put_u64(&cursor, fp_fnv1a_bytes(buffer, cursor.offset));
}

fp_result fp_state_write_atomic(const char *path, const fp_state *state)
{
    fp_atomic_file file;
    unsigned char *buffer;
    size_t size;
    fp_result result;

    if (path == NULL || fp_state_validate(state) != FP_OK) {
        return FP_INVALID;
    }
    size = serialized_size(state->dimension, state->point_count);
    buffer = malloc(size);
    if (buffer == NULL) {
        return FP_IO;
    }
    serialize_state(state, buffer, size);
    result = fp_atomic_begin(path, "wb", &file);
    if (result == FP_OK && fwrite(buffer, 1, size, file.stream) != size) {
        result = FP_IO;
    }
    free(buffer);
    if (result != FP_OK) {
        fp_atomic_abort(&file);
        return result;
    }
    return fp_atomic_commit(&file);
}

static fp_result read_checkpoint(const char *path, unsigned char **buffer, size_t *size)
{
    unsigned char *data;
    FILE *stream;
    size_t count;

    errno = 0;
    stream = fopen(path, "rb");
    if (stream == NULL) {
        return errno == ENOENT ? FP_MISSING : FP_IO;
    }
    data = malloc(FP_STATE_MAX_SIZE + 1u);
    if (data == NULL) {
        (void)fclose(stream);
        return FP_IO;
    }
    count = fread(data, 1, FP_STATE_MAX_SIZE + 1u, stream);
    if (ferror(stream)) {
        free(data);
        (void)fclose(stream);
        return FP_IO;
    }
    if (fclose(stream) != 0) {
        free(data);
        return FP_IO;
    }
    if (count > FP_STATE_MAX_SIZE) {
        free(data);
        return FP_INVALID;
    }
    *buffer = data;
    *size = count;
    return FP_OK;
}

fp_result fp_state_load(const char *path, fp_state *state)
{
    unsigned char *buffer = NULL;
    size_t size = 0;
    byte_cursor cursor;
    fp_state parsed;
    uint32_t version;
    uint32_t dimension;
    uint32_t status;
    uint32_t point_count;
    uint32_t fold_count;
    uint32_t retained_sign;
    uint64_t reserved64;
    uint32_t reserved32;
    uint64_t stored_checksum;
    uint64_t computed_checksum;
    size_t expected;
    size_t index;
    fp_result result;

    if (path == NULL || state == NULL) {
        return FP_INVALID;
    }
    result = read_checkpoint(path, &buffer, &size);
    if (result != FP_OK) {
        return result;
    }
    if (size < FP_STATE_HEADER_SIZE + FP_STATE_TRAILER_SIZE ||
        memcmp(buffer, state_magic, sizeof(state_magic)) != 0) {
        free(buffer);
        return FP_INVALID;
    }
    cursor.data = buffer;
    cursor.size = size;
    cursor.offset = sizeof(state_magic);
    memset(&parsed, 0, sizeof(parsed));
    if (!get_u32(&cursor, &version) || !get_u32(&cursor, &dimension) ||
        !get_u64(&cursor, &parsed.model_fingerprint) ||
        !get_u64(&cursor, &parsed.control_fingerprint) || !get_u32(&cursor, &status) ||
        !get_u32(&cursor, &point_count) || !get_u32(&cursor, &fold_count) ||
        !get_u32(&cursor, &retained_sign) || !get_double(&cursor, &parsed.next_step) ||
        !get_u64(&cursor, &reserved64) || !get_u32(&cursor, &reserved32) ||
        version != FP_STATE_VERSION || dimension == 0 || dimension > FP_MAX_DIM ||
        point_count == 0 || point_count > FP_MAX_POINTS || reserved64 != 0 || reserved32 != 0) {
        free(buffer);
        return FP_INVALID;
    }
    expected = serialized_size(dimension, point_count);
    if (size != expected) {
        free(buffer);
        return FP_INVALID;
    }
    cursor.offset = size - FP_STATE_TRAILER_SIZE;
    if (!get_u64(&cursor, &stored_checksum)) {
        free(buffer);
        return FP_INVALID;
    }
    computed_checksum = fp_fnv1a_bytes(buffer, size - FP_STATE_TRAILER_SIZE);
    if (stored_checksum != computed_checksum) {
        free(buffer);
        return FP_INVALID;
    }

    parsed.dimension = dimension;
    parsed.status = (fp_status)status;
    parsed.point_count = point_count;
    parsed.fold_count = fold_count;
    parsed.retained_fold_sign = (int)(int32_t)retained_sign;
    cursor.offset = FP_STATE_HEADER_SIZE;
    cursor.size = size - FP_STATE_TRAILER_SIZE;
    for (index = 0; index < parsed.point_count; ++index) {
        fp_point *point = &parsed.points[index];
        uint32_t point_index;
        uint32_t iterations;
        uint32_t fold;
        uint32_t reserved;
        size_t component;

        if (!get_u32(&cursor, &point_index) || !get_u32(&cursor, &iterations) ||
            !get_u32(&cursor, &fold) || !get_u32(&cursor, &reserved) || reserved != 0 ||
            !get_double(&cursor, &point->arclength) ||
            !get_double(&cursor, &point->step_used) ||
            !get_double(&cursor, &point->lambda) ||
            !get_double(&cursor, &point->residual_inf)) {
            free(buffer);
            return FP_INVALID;
        }
        point->index = point_index;
        point->newton_iterations = iterations;
        point->fold = (fp_fold)fold;
        for (component = 0; component < parsed.dimension; ++component) {
            if (!get_double(&cursor, &point->x[component])) {
                free(buffer);
                return FP_INVALID;
            }
        }
        for (component = 0; component < parsed.dimension + 1; ++component) {
            if (!get_double(&cursor, &point->tangent[component])) {
                free(buffer);
                return FP_INVALID;
            }
        }
    }
    free(buffer);
    if (cursor.offset != cursor.size || fp_state_validate(&parsed) != FP_OK) {
        return FP_INVALID;
    }
    *state = parsed;
    return FP_OK;
}
