#include "dyeworks/uleb.h"

#include <string.h>

#include "dyeworks/error.h"

#define ULEB_MAX_BYTES 10 /* a 64-bit value needs at most ten 7-bit groups */

/* LEB128 varints encode an integer in 7-bit groups, low group first, with the
 * high bit of each byte set while more groups follow. The decoder walks
 * continuation bytes until it meets one whose high bit is clear, never reading
 * past end and never accepting a varint whose value does not fit in 64 bits. */
int uleb_decode(const uint8_t *buf, size_t p, size_t end, uint64_t *out,
                size_t *consumed) {
    uint64_t value = 0;
    unsigned shift = 0;
    size_t start = p;
    size_t count = 0;

    for (;;) {
        if (p >= end) {
            return dyeworks_error("uleb", "varint runs past end of section");
        }
        if (count >= ULEB_MAX_BYTES) {
            return dyeworks_error("uleb", "over-long varint");
        }
        uint8_t byte = buf[p++];
        count++;
        uint64_t payload = (uint64_t)(byte & 0x7f);
        /* Nine 7-bit groups fill bits 0..62; the tenth group lands at bit 63, so
         * only its lowest bit fits a uint64. A larger payload there would shift
         * bits out and silently lose them, so reject it as an overflow rather
         * than decode a truncated value. */
        if (shift == 63 && payload > 1) {
            return dyeworks_error("uleb", "varint value does not fit in 64 bits");
        }
        value |= payload << shift;
        if ((byte & 0x80) == 0) {
            break;
        }
        shift += 7;
    }

    *out = value;
    *consumed = p - start;
    return 0;
}

/* The signed decoder accumulates through an unsigned integer so no shift ever
 * overflows a signed value, validates that the final group fits a signed 64-bit
 * value, then sign-extends by hand. */
int sleb_decode(const uint8_t *buf, size_t p, size_t end, int64_t *out,
                size_t *consumed) {
    uint64_t value = 0;
    unsigned shift = 0;
    size_t start = p;
    size_t count = 0;
    uint8_t byte;

    do {
        if (p >= end) {
            return dyeworks_error("uleb", "signed varint runs past end of section");
        }
        if (count >= ULEB_MAX_BYTES) {
            return dyeworks_error("uleb", "over-long signed varint");
        }
        byte = buf[p++];
        count++;
        uint64_t payload = (uint64_t)(byte & 0x7f);
        /* The tenth group lands at bit 63, the sign bit. A well-formed signed
         * value sign-extends there, so the final group's payload must be all
         * zero (0x00) for a non-negative value or all one (0x7f) for a negative
         * one; anything else overflows a signed 64-bit value. */
        if (shift == 63 && payload != 0x00 && payload != 0x7f) {
            return dyeworks_error("uleb",
                               "signed varint value does not fit in 64 bits");
        }
        value |= payload << shift;
        shift += 7;
    } while (byte & 0x80);

    /* Sign-extend when the final group's sign bit is set and bits remain above
     * what was written; the accumulation above never touched a signed value. */
    if (shift < 64 && (byte & 0x40)) {
        value |= ~(uint64_t)0 << shift;
    }

    int64_t result;
    memcpy(&result, &value, sizeof result);
    *out = result;
    *consumed = p - start;
    return 0;
}
