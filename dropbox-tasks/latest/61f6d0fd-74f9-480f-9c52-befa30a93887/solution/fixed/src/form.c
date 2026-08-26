#include "dyeworks/form.h"

#include "dyeworks/error.h"
#include "dyeworks/reader.h"
#include "dyeworks/lot.h"
#include "dyeworks/str.h"
#include "dyeworks/uleb.h"

/* Param value form codes understood by the reduced reader. */
#define FORM_data1 0x01
#define FORM_data2 0x02
#define FORM_data4 0x03
#define FORM_data8 0x04
#define FORM_uleb 0x05
#define FORM_sleb 0x06
#define FORM_str 0x07
#define FORM_string 0x08
#define FORM_block1 0x09
#define FORM_block2 0x0a
#define FORM_block4 0x0b
#define FORM_flag 0x0c
#define FORM_indirect 0x10
#define FORM_lot 0x11

/* Each form determines how many bytes of the node its value occupies. A str
 * value is a four-byte offset into the strings section naming a string; a lot
 * value is a four-byte index into the lots table; a block1 value is a one-byte
 * length followed by that many bytes; an inline string runs to its terminating
 * NUL. Every read is bounded against the unit and, for str and lot, against
 * the section it resolves into. */
static int fits(size_t q, size_t need, size_t unit_end) {
    return q <= unit_end && need <= unit_end - q;
}

int form_consume(dyeworks_t *sp, uint64_t form, size_t *p, size_t unit_end) {
    const uint8_t *b = sp->buf;
    size_t q = *p;

    switch (form) {
        case FORM_data1:
            if (!fits(q, 1, unit_end)) {
                return dyeworks_error("form", "data1 value past end of unit");
            }
            q += 1;
            break;
        case FORM_data2:
            if (!fits(q, 2, unit_end)) {
                return dyeworks_error("form", "data2 value past end of unit");
            }
            q += 2;
            break;
        case FORM_data4:
            if (!fits(q, 4, unit_end)) {
                return dyeworks_error("form", "data4 value past end of unit");
            }
            q += 4;
            break;
        case FORM_data8:
            if (!fits(q, 8, unit_end)) {
                return dyeworks_error("form", "data8 value past end of unit");
            }
            q += 8;
            break;
        case FORM_flag:
            break;
        case FORM_uleb: {
            uint64_t v;
            size_t used;
            if (uleb_decode(b, q, unit_end, &v, &used) < 0) {
                return -1;
            }
            q += used;
            break;
        }
        case FORM_sleb: {
            int64_t v;
            size_t used;
            if (sleb_decode(b, q, unit_end, &v, &used) < 0) {
                return -1;
            }
            q += used;
            break;
        }
        case FORM_block1: {
            if (!fits(q, 1, unit_end)) {
                return dyeworks_error("form", "block1 length past end of unit");
            }
            uint8_t len = b[q];
            if (!fits(q + 1, len, unit_end)) {
                return dyeworks_error("form", "block1 data past end of unit");
            }
            q += 1 + len;
            break;
        }
        case FORM_block2: {
            if (!fits(q, 2, unit_end)) {
                return dyeworks_error("form", "block2 length past end of unit");
            }
            uint16_t len = rd_u16(b, q);
            if (!fits(q + 2, len, unit_end)) {
                return dyeworks_error("form", "block2 data past end of unit");
            }
            q += 2 + (size_t)len;
            break;
        }
        case FORM_block4: {
            if (!fits(q, 4, unit_end)) {
                return dyeworks_error("form", "block4 length past end of unit");
            }
            uint32_t len = rd_u32(b, q);
            if (!fits(q + 4, len, unit_end)) {
                return dyeworks_error("form", "block4 data past end of unit");
            }
            q += 4 + (size_t)len;
            break;
        }
        case FORM_indirect: {
            uint64_t real_form;
            size_t used;
            if (uleb_decode(b, q, unit_end, &real_form, &used) < 0) {
                return -1;
            }
            if (real_form == FORM_indirect) {
                return dyeworks_error("form", "indirect form names itself");
            }
            q += used;
            sp->indirects_resolved++;
            *p = q;
            return form_consume(sp, real_form, p, unit_end);
        }
        case FORM_string: {
            while (q < unit_end && b[q] != 0) {
                q++;
            }
            if (q >= unit_end) {
                return dyeworks_error("form", "inline string past end of unit");
            }
            q++;
            break;
        }
        case FORM_str: {
            if (!fits(q, 4, unit_end)) {
                return dyeworks_error("form", "str offset past end of unit");
            }
            uint32_t stroff = rd_u32(b, q);
            q += 4;
            if (str_check(sp, stroff) < 0) {
                return -1;
            }
            break;
        }
        case FORM_lot: {
            if (!fits(q, 4, unit_end)) {
                return dyeworks_error("form", "lot ref past end of unit");
            }
            uint32_t idx = rd_u32(b, q);
            q += 4;
            if (lot_check(sp, idx) < 0) {
                return -1;
            }
            break;
        }
        default:
            return dyeworks_error("form", "unknown param form 0x%llx",
                               (unsigned long long)form);
    }

    *p = q;
    return 0;
}
