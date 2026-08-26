#ifndef IMG_BYTES_H
#define IMG_BYTES_H

#include <stdint.h>

/* Big-endian fixed-width readers. These read the requested width at p; keeping
 * the read inside the region is the caller's responsibility. */
static inline uint16_t img_rd_u16(const uint8_t *p) {
    return (uint16_t)((uint16_t)p[0] << 8 | (uint16_t)p[1]);
}

static inline uint32_t img_rd_u32(const uint8_t *p) {
    return (uint32_t)p[0] << 24 | (uint32_t)p[1] << 16 | (uint32_t)p[2] << 8 |
           (uint32_t)p[3];
}

#endif
