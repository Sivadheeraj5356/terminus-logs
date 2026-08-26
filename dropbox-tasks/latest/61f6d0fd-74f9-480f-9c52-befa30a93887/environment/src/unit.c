#include "dyeworks/unit.h"

#include "dyeworks/error.h"
#include "dyeworks/reader.h"

#define DYEWORKS_UNIT_HEADER 15 /* unit_length, version, dyeworksdef_offset, reserved, node_count */

/* The nodes section opens with a unit header: a unit length covering the rest
 * of the unit, the format version, the offset of this unit's dyeworksdef inside
 * the dyeworksdef section, a reserved byte, and the number of node records the
 * unit pre-sizes its table for. The nodes follow the header. */
int unit_parse(dyeworks_t *sp) {
    const uint8_t *b = sp->buf;
    size_t o = sp->sec[DYEWORKS_SEC_NODES].off;
    size_t tsize = sp->sec[DYEWORKS_SEC_NODES].size;

    if (tsize < DYEWORKS_UNIT_HEADER) {
        return dyeworks_error("node", "unit header truncated");
    }

    uint32_t unit_length = rd_u32(b, o + 0);
    sp->unit_version = rd_u16(b, o + 4);
    sp->dyeworksdef_offset = rd_u32(b, o + 6);
    /* reserved byte at o + 10 is recorded but not otherwise used */
    sp->node_count = rd_u32(b, o + 11);

    sp->node_start = o + DYEWORKS_UNIT_HEADER;
    sp->unit_end = o + 4 + unit_length;

    return 0;
}
