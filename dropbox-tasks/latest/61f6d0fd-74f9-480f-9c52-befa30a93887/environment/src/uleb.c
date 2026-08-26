#include "dyeworks/uleb.h"

#include "dyeworks/error.h"

/* LEB128 varints encode an integer in 7-bit groups, low group first, with the
 * high bit of each byte set while more groups follow. The decoder walks
 * continuation bytes until it meets one whose high bit is clear. */
int uleb_decode(const uint8_t *buf, size_t p, size_t end, uint64_t *out,
                size_t *consumed) {
    (void)end;
    uint64_t value = 0;
    unsigned shift = 0;
    size_t start = p;

    for (;;) {
        uint8_t byte = buf[p++];
        value |= (uint64_t)(byte & 0x7f) << shift;
        if ((byte & 0x80) == 0) {
            break;
        }
        shift += 7;
    }

    *out = value;
    *consumed = p - start;
    return 0;
}

int sleb_decode(const uint8_t *buf, size_t p, size_t end, int64_t *out,
                size_t *consumed) {
    (void)end;
    int64_t value = 0;
    unsigned shift = 0;
    size_t start = p;
    uint8_t byte;

    do {
        byte = buf[p++];
        value |= (int64_t)(byte & 0x7f) << shift;
        shift += 7;
    } while (byte & 0x80);

    if (shift < 64 && (byte & 0x40)) {
        value |= -((int64_t)1 << shift);
    }

    *out = value;
    *consumed = p - start;
    return 0;
}
