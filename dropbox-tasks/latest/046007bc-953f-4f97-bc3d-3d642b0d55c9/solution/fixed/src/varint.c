#include "img/varint.h"

#include "img/error.h"

#define IMG_ULEB_MAX_BYTES 10 /* a 64-bit value needs at most ten 7-bit groups */

/* LEB128 varints encode an integer in 7-bit groups, low group first, with the
 * high bit of each byte set while more groups follow. The decoder walks
 * continuation bytes until it meets one whose high bit is clear, never reading
 * past end and never accepting a varint too long to fit in 64 bits. */
int img_uleb(const uint8_t *buf, size_t p, size_t end, uint64_t *out,
             size_t *consumed) {
    uint64_t value = 0;
    unsigned shift = 0;
    size_t start = p;
    size_t count = 0;

    for (;;) {
        if (p >= end) {
            return img_error("uleb", "varint runs past end of region");
        }
        if (count >= IMG_ULEB_MAX_BYTES) {
            return img_error("uleb", "over-long varint");
        }
        uint8_t byte = buf[p++];
        count++;
        if (shift < 64) {
            value |= (uint64_t)(byte & 0x7f) << shift;
        }
        if ((byte & 0x80) == 0) {
            break;
        }
        shift += 7;
    }

    *out = value;
    *consumed = p - start;
    return 0;
}

int img_sleb(const uint8_t *buf, size_t p, size_t end, int64_t *out,
             size_t *consumed) {
    int64_t value = 0;
    unsigned shift = 0;
    size_t start = p;
    size_t count = 0;
    uint8_t byte;

    do {
        if (p >= end) {
            return img_error("uleb", "signed varint runs past end of region");
        }
        if (count >= IMG_ULEB_MAX_BYTES) {
            return img_error("uleb", "over-long signed varint");
        }
        byte = buf[p++];
        count++;
        if (shift < 64) {
            value |= (int64_t)(byte & 0x7f) << shift;
        }
        shift += 7;
    } while (byte & 0x80);

    if (shift < 64 && (byte & 0x40)) {
        value |= -((int64_t)1 << shift);
    }

    *out = value;
    *consumed = p - start;
    return 0;
}
