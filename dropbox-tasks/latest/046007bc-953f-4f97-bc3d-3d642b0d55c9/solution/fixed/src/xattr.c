#include "img/xattr.h"

#include "img/error.h"
#include "img/varint.h"

/* Parses the xattr table: a ULEB count followed by that many attributes, each an
 * inode index, a ULEB key, and an inline value given by a ULEB length and then
 * that many value bytes. The value is confirmed to lie within the region before
 * it is scanned. */
int img_xattr_parse(img_image_t *c) {
    if (c->xattrs_size == 0) {
        c->xattr_count = 0;
        return 0;
    }
    size_t base = (size_t)(c->xattrs - c->buf);
    size_t end = base + c->xattrs_size;
    size_t p = base;
    size_t used;

    uint64_t count;
    if (img_uleb(c->buf, p, end, &count, &used) < 0) {
        return -1;
    }
    p += used;
    c->xattr_count = count;

    for (uint64_t i = 0; i < count; i++) {
        uint64_t inode_index, key, vlen;
        if (img_uleb(c->buf, p, end, &inode_index, &used) < 0) {
            return -1;
        }
        p += used;
        if (img_uleb(c->buf, p, end, &key, &used) < 0) {
            return -1;
        }
        p += used;
        if (img_uleb(c->buf, p, end, &vlen, &used) < 0) {
            return -1;
        }
        p += used;
        (void)inode_index;
        (void)key;

        if (vlen > end - p) {
            return img_error("xattr", "value runs past end of region");
        }
        for (uint64_t j = 0; j < vlen; j++) {
            c->xattr_checksum += c->buf[p + j];
        }
        p += vlen;
    }
    return 0;
}
