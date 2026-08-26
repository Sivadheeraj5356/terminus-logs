#include "foldpath/fingerprint.h"

#include <stdio.h>

#define FP_FNV_OFFSET UINT64_C(14695981039346656037)
#define FP_FNV_PRIME UINT64_C(1099511628211)

static uint64_t fnv_update(uint64_t hash, const unsigned char *data, size_t length)
{
    size_t index;

    for (index = 0; index < length; ++index) {
        hash ^= (uint64_t)data[index];
        hash *= FP_FNV_PRIME;
    }
    return hash;
}

uint64_t fp_fnv1a_bytes(const void *data, size_t length)
{
    return fnv_update(FP_FNV_OFFSET, (const unsigned char *)data, length);
}

fp_result fp_fnv1a_file(const char *path, uint64_t *fingerprint)
{
    unsigned char buffer[8192];
    uint64_t hash = FP_FNV_OFFSET;
    FILE *stream;

    if (path == NULL || fingerprint == NULL) {
        return FP_INVALID;
    }
    stream = fopen(path, "rb");
    if (stream == NULL) {
        return FP_IO;
    }
    for (;;) {
        size_t count = fread(buffer, 1, sizeof(buffer), stream);

        hash = fnv_update(hash, buffer, count);
        if (count < sizeof(buffer)) {
            if (ferror(stream)) {
                (void)fclose(stream);
                return FP_IO;
            }
            break;
        }
    }
    if (fclose(stream) != 0) {
        return FP_IO;
    }
    *fingerprint = hash;
    return FP_OK;
}
