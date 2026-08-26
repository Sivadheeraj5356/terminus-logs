#ifndef FOLDPATH_FINGERPRINT_H
#define FOLDPATH_FINGERPRINT_H

#include "foldpath/types.h"

uint64_t fp_fnv1a_bytes(const void *data, size_t length);
fp_result fp_fnv1a_file(const char *path, uint64_t *fingerprint);

#endif
