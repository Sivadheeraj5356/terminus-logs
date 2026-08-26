#include "foldpath/fingerprint.h"

/*
 * Deliberate task scaffold. FNV-1a byte hashing and robust whole-file hashing
 * must be completed for checkpoint identity and integrity.
 */

uint64_t fp_fnv1a_bytes(const void *data, size_t length)
{
    (void)data;
    (void)length;
    return UINT64_C(0);
}

fp_result fp_fnv1a_file(const char *path, uint64_t *fingerprint)
{
    (void)path;
    (void)fingerprint;
    return FP_INVALID;
}
