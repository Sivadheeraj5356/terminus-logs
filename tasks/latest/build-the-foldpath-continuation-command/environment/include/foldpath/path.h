#ifndef FOLDPATH_PATH_H
#define FOLDPATH_PATH_H

#include "foldpath/types.h"

#include <stdio.h>

typedef struct {
    FILE *stream;
    char *temporary_path;
    char *target_path;
} fp_atomic_file;

int fp_path_is_absolute(const char *path);
int fp_paths_equal(const char *left, const char *right);
fp_result fp_atomic_begin(const char *target_path, const char *mode, fp_atomic_file *file);
fp_result fp_atomic_commit(fp_atomic_file *file);
void fp_atomic_abort(fp_atomic_file *file);

#endif
