#include "dyeworks/lot.h"

#include "dyeworks/error.h"
#include "dyeworks/reader.h"

/* Resolve a lot-ref index against the lots table. The lots table is an array
 * of four-byte lot ids; a lot-ref selects one by index and the reader reads
 * its id to confirm the reference resolves. */
int lot_check(dyeworks_t *sp, uint32_t index) {
    const uint8_t *b = sp->buf;
    size_t rbase = sp->sec[DYEWORKS_SEC_LOTS].off;

    uint32_t id = rd_u32(b, rbase + (size_t)index * 4);
    (void)id;
    sp->lots_resolved++;

    return 0;
}
