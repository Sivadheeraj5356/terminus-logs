#include "dyeworks/sectab.h"

#include "dyeworks/error.h"
#include "dyeworks/reader.h"

#define DYEWORKS_HEADER_SIZE 8
#define DYEWORKS_SECENT_SIZE 9

/* The container opens with an eight-byte header (a four-byte magic, a version
 * byte, and a section count) followed by a table of fixed-size entries, each
 * naming a section and giving its byte offset and size inside the file. */
int sectab_parse(dyeworks_t *sp) {
    const uint8_t *b = sp->buf;

    if (sp->n < DYEWORKS_HEADER_SIZE) {
        return dyeworks_error("header", "file too small for a container header");
    }
    if (rd_u32(b, 0) != DYEWORKS_MAGIC) {
        return dyeworks_error("header", "bad container magic");
    }
    sp->version = b[4];
    uint8_t nsections = b[5];
    if (nsections != DYEWORKS_NSECTIONS) {
        return dyeworks_error("header", "expected %u sections, found %u",
                           DYEWORKS_NSECTIONS, nsections);
    }

    size_t tab = DYEWORKS_HEADER_SIZE;
    if (sp->n - DYEWORKS_HEADER_SIZE < (size_t)nsections * DYEWORKS_SECENT_SIZE) {
        return dyeworks_error("header", "section table runs past end of file");
    }

    for (uint8_t i = 0; i < nsections; i++) {
        size_t e = tab + (size_t)i * DYEWORKS_SECENT_SIZE;
        uint8_t name = b[e];
        uint32_t off = rd_u32(b, e + 1);
        uint32_t size = rd_u32(b, e + 5);

        if (name >= DYEWORKS_NSECTIONS) {
            return dyeworks_error("header", "unknown section name %u", name);
        }

        sp->sec[name].off = off;
        sp->sec[name].size = size;
        sp->sec[name].present = 1;
    }

    for (int i = 0; i < DYEWORKS_NSECTIONS; i++) {
        if (!sp->sec[i].present) {
            return dyeworks_error("header", "missing section %d", i);
        }
    }

    return 0;
}
