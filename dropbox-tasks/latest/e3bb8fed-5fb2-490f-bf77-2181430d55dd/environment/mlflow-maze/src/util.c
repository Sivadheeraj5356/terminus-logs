#include "maze/util.h"

int maze_absolute_path(const char *path) {
    return path != NULL && path[0] == '/';
}

int maze_read_file(const char *path, unsigned char **data, size_t *size) {
    (void)path;
    (void)data;
    (void)size;
    return -1;
}

void maze_sha256(const void *data, size_t size, char output[65]) {
    (void)data;
    (void)size;
    if (output != NULL) {
        output[0] = '\0';
    }
}

int maze_atomic_write(const char *path, const void *data, size_t size) {
    (void)path;
    (void)data;
    (void)size;
    return -1;
}
