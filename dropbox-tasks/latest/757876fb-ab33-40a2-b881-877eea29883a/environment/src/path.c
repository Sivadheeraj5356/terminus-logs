#include "foldpath/path.h"

#include <string.h>

/*
 * Absolute-path and lexical-conflict checks are ready for both commands.
 * Crash-safe sibling temporary-file creation, commit, and cleanup are
 * intentionally left for the continuation implementation.
 */

int fp_path_is_absolute(const char *path)
{
    return path != NULL && path[0] == '/';
}

int fp_paths_equal(const char *left, const char *right)
{
    return left != NULL && right != NULL && strcmp(left, right) == 0;
}

fp_result fp_atomic_begin(const char *target_path, const char *mode, fp_atomic_file *file)
{
    (void)target_path;
    (void)mode;
    (void)file;
    return FP_INVALID;
}

fp_result fp_atomic_commit(fp_atomic_file *file)
{
    (void)file;
    return FP_INVALID;
}

void fp_atomic_abort(fp_atomic_file *file)
{
    (void)file;
}
