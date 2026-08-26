#define _POSIX_C_SOURCE 200809L

#include "foldpath/path.h"

#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

static void atomic_reset(fp_atomic_file *file)
{
    file->stream = NULL;
    file->temporary_path = NULL;
    file->target_path = NULL;
}

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
    static const char suffix[] = ".tmp.XXXXXX";
    size_t length;
    int descriptor;

    if (target_path == NULL || mode == NULL || file == NULL) {
        return FP_INVALID;
    }
    atomic_reset(file);
    length = strlen(target_path);
    if (length > SIZE_MAX - sizeof(suffix)) {
        return FP_IO;
    }
    file->temporary_path = malloc(length + sizeof(suffix));
    if (file->temporary_path != NULL) {
        file->temporary_path[0] = '\0';
    }
    file->target_path = strdup(target_path);
    if (file->temporary_path == NULL || file->target_path == NULL) {
        free(file->temporary_path);
        free(file->target_path);
        atomic_reset(file);
        return FP_IO;
    }
    memcpy(file->temporary_path, target_path, length);
    memcpy(file->temporary_path + length, suffix, sizeof(suffix));
    descriptor = mkstemp(file->temporary_path);
    if (descriptor < 0) {
        fp_atomic_abort(file);
        return FP_IO;
    }
    if (fchmod(descriptor, S_IRUSR | S_IWUSR | S_IRGRP | S_IROTH) != 0) {
        (void)close(descriptor);
        (void)unlink(file->temporary_path);
        fp_atomic_abort(file);
        return FP_IO;
    }
    file->stream = fdopen(descriptor, mode);
    if (file->stream == NULL) {
        (void)close(descriptor);
        (void)unlink(file->temporary_path);
        fp_atomic_abort(file);
        return FP_IO;
    }
    return FP_OK;
}

fp_result fp_atomic_commit(fp_atomic_file *file)
{
    int descriptor;
    int failed = 0;

    if (file == NULL || file->stream == NULL || file->temporary_path == NULL ||
        file->target_path == NULL) {
        return FP_INVALID;
    }
    if (fflush(file->stream) != 0) {
        failed = 1;
    }
    descriptor = fileno(file->stream);
    if (!failed && (descriptor < 0 || fsync(descriptor) != 0)) {
        failed = 1;
    }
    if (fclose(file->stream) != 0) {
        failed = 1;
    }
    file->stream = NULL;
    if (!failed && rename(file->temporary_path, file->target_path) != 0) {
        failed = 1;
    }
    if (failed) {
        (void)unlink(file->temporary_path);
    }
    free(file->temporary_path);
    free(file->target_path);
    atomic_reset(file);
    return failed ? FP_IO : FP_OK;
}

void fp_atomic_abort(fp_atomic_file *file)
{
    if (file == NULL) {
        return;
    }
    if (file->stream != NULL) {
        (void)fclose(file->stream);
    }
    if (file->temporary_path != NULL) {
        (void)unlink(file->temporary_path);
    }
    free(file->temporary_path);
    free(file->target_path);
    atomic_reset(file);
}
