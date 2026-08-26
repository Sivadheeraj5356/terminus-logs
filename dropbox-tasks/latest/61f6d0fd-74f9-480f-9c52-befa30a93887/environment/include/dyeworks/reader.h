#ifndef DYEWORKS_READER_H
#define DYEWORKS_READER_H

#include <stddef.h>
#include <stdint.h>

int dyeworks_load_file(const char *path, uint8_t **buf, size_t *n);

/* All multi-byte container integers are big-endian. */
static inline uint16_t rd_u16(const uint8_t *b, size_t off) {
    return (uint16_t)(((uint16_t)b[off] << 8) | (uint16_t)b[off + 1]);
}

static inline uint32_t rd_u32(const uint8_t *b, size_t off) {
    return ((uint32_t)b[off] << 24) | ((uint32_t)b[off + 1] << 16) |
           ((uint32_t)b[off + 2] << 8) | (uint32_t)b[off + 3];
}

#endif
