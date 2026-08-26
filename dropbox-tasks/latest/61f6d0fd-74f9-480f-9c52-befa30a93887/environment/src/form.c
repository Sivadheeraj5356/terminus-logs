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
 * NUL. */
int form_consume(dyeworks_t *sp, uint64_t form, size_t *p, size_t unit_end) {
    (void)unit_end;
    const uint8_t *b = sp->buf;
    size_t q = *p;

    switch (form) {
        case FORM_data1:
            q += 1;
            break;
        case FORM_data2:
            q += 2;
            break;
        case FORM_data4:
            q += 4;
            break;
        case FORM_data8:
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
            uint8_t len = b[q];
            q += 1 + len;
            break;
        }
        case FORM_block2: {
            uint16_t len = rd_u16(b, q);
            q += 2 + (size_t)len;
            break;
        }
        case FORM_block4: {
            uint32_t len = rd_u32(b, q);
            q += 4 + (size_t)len;
            break;
        }
        case FORM_indirect: {
            uint64_t real_form;
            size_t used;
            if (uleb_decode(b, q, unit_end, &real_form, &used) < 0) {
                return -1;
            }
            q += used;
            sp->indirects_resolved++;
            *p = q;
            return form_consume(sp, real_form, p, unit_end);
        }
        case FORM_string: {
            while (b[q] != 0) {
                q++;
            }
            q++;
            break;
        }
        case FORM_str: {
            uint32_t stroff = rd_u32(b, q);
            q += 4;
            if (str_check(sp, stroff) < 0) {
                return -1;
            }
            break;
        }
        case FORM_lot: {
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
