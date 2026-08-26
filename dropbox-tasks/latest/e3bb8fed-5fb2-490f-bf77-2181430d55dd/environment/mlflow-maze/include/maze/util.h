#ifndef MAZE_UTIL_H
#define MAZE_UTIL_H

#include <stddef.h>

int maze_absolute_path(const char *path);
int maze_read_file(const char *path, unsigned char **data, size_t *size);
void maze_sha256(const void *data, size_t size, char output[65]);
int maze_atomic_write(const char *path, const void *data, size_t size);

#endif
