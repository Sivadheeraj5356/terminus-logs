#ifndef DYEWORKS_ULEB_H
#define DYEWORKS_ULEB_H

#include <stddef.h>
#include <stdint.h>

/* Decode an unsigned LEB128 varint starting at buf[p], reading no further than
 * end. On success returns 0, writes the value to *out and the number of bytes
 * consumed to *consumed. */
int uleb_decode(const uint8_t *buf, size_t p, size_t end, uint64_t *out,
                size_t *consumed);

/* Decode a signed LEB128 varint with the same bounds contract. */
int sleb_decode(const uint8_t *buf, size_t p, size_t end, int64_t *out,
                size_t *consumed);

#endif
