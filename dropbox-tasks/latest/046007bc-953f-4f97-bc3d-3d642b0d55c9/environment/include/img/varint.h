#ifndef IMG_VARINT_H
#define IMG_VARINT_H

#include <stddef.h>
#include <stdint.h>

/* LEB128 varint decoders. On success return 0, write the decoded value to *out,
 * and set *consumed to the number of bytes read; on a malformed varint return
 * -1 after reporting the `uleb` subsystem. */
int img_uleb(const uint8_t *buf, size_t p, size_t end, uint64_t *out,
             size_t *consumed);
int img_sleb(const uint8_t *buf, size_t p, size_t end, int64_t *out,
             size_t *consumed);

#endif
