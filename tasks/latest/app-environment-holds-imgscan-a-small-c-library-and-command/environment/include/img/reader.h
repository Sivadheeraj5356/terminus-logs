#ifndef IMG_READER_H
#define IMG_READER_H

#include <stddef.h>
#include <stdint.h>

/* Reads the whole file into a freshly allocated buffer. Returns 0 and sets the
 * buffer and length on success, -1 on failure. The caller frees the buffer. */
int img_load_file(const char *path, uint8_t **buf, size_t *len);

#endif
