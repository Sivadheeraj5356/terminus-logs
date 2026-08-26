#include "img/link.h"

#include "img/error.h"
#include "img/varint.h"

/* Parses the hardlink table: a ULEB count followed by that many edges, each a
 * first inode index, a second inode index, and a signed weight. Both members of
 * each edge are looked up in the inode array. */
int img_link_parse(img_image_t *c) {
    if (c->links_size == 0) {
        c->link_count = 0;
        return 0;
    }
    size_t base = (size_t)(c->links - c->buf);
    size_t end = base + c->links_size;
    size_t p = base;
    size_t used;

    uint64_t count;
    if (img_uleb(c->buf, p, end, &count, &used) < 0) {
        return -1;
    }
    p += used;
    c->link_count = count;

    for (uint64_t i = 0; i < count; i++) {
        uint64_t a, b;
        int64_t weight;
        if (img_uleb(c->buf, p, end, &a, &used) < 0) {
            return -1;
        }
        p += used;
        if (img_uleb(c->buf, p, end, &b, &used) < 0) {
            return -1;
        }
        p += used;
        if (img_sleb(c->buf, p, end, &weight, &used) < 0) {
            return -1;
        }
        p += used;

        c->link_checksum += c->inode[a].uid;
        c->link_checksum += c->inode[b].uid;
        c->link_checksum += (uint64_t)weight;
    }
    return 0;
}
