#include "img/vol.h"

#include "img/bytes.h"
#include "img/error.h"
#include "img/varint.h"

/* Walks the names pool from a volume's label offset to its terminating NUL,
 * confirming the label lies wholly within the names pool. */
static int scan_label(const img_image_t *c, uint32_t label_off) {
    if (c->names == 0 || label_off >= c->names_size) {
        return img_error("name", "label offset out of range");
    }
    for (size_t k = label_off; k < c->names_size; k++) {
        if (c->names[k] == 0) {
            return 0;
        }
    }
    return img_error("name", "label not terminated within pool");
}

/* Parses the volume descriptor table: a ULEB count followed by that many
 * descriptors, each a four-byte label offset into the names pool, a signed base
 * LBA, and a ULEB feature-flags word. Each fixed-width field read is bounded
 * against the region before it is taken. */
int img_vol_parse(img_image_t *c) {
    if (c->volumes_size == 0) {
        c->volume_count = 0;
        return 0;
    }
    size_t base = (size_t)(c->volumes - c->buf);
    size_t end = base + c->volumes_size;
    size_t p = base;
    size_t used;

    uint64_t count;
    if (img_uleb(c->buf, p, end, &count, &used) < 0) {
        return -1;
    }
    p += used;
    c->volume_count = count;

    for (uint64_t i = 0; i < count; i++) {
        if (p + 4 > end) {
            return img_error("vol", "label offset past region");
        }
        uint32_t label_off = img_rd_u32(c->buf + p);
        p += 4;

        int64_t base_lba;
        if (img_sleb(c->buf, p, end, &base_lba, &used) < 0) {
            return -1;
        }
        p += used;

        uint64_t flags;
        if (img_uleb(c->buf, p, end, &flags, &used) < 0) {
            return -1;
        }
        p += used;
        (void)base_lba;
        (void)flags;

        if (scan_label(c, label_off) < 0) {
            return -1;
        }
        c->vol_checksum += label_off;
    }
    return 0;
}
