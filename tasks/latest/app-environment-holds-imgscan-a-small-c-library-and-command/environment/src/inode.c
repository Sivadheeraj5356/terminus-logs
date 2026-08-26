#include "img/inode.h"

#include <stdlib.h>

#include "img/bytes.h"
#include "img/error.h"
#include "img/varint.h"

/* Parses the inode table: a ULEB count followed by that many inodes. Each inode
 * is a four-byte uid, a signed modification-time delta, a kind byte, and then
 * either a run of resident data bytes (a file) or a list of child inode indices
 * (a directory). */
int img_inode_parse(img_image_t *c) {
    if (c->inodes_size == 0) {
        c->inode_count = 0;
        return 0;
    }
    size_t base = (size_t)(c->inodes - c->buf);
    size_t end = base + c->inodes_size;
    size_t p = base;
    size_t used;

    uint64_t count;
    if (img_uleb(c->buf, p, end, &count, &used) < 0) {
        return -1;
    }
    p += used;

    uint32_t bytes = (uint32_t)count * (uint32_t)sizeof(img_inode_t);
    c->inode = malloc(bytes);
    if (!c->inode && count) {
        return img_error("inode", "out of memory");
    }
    c->inode_count = count;

    for (uint64_t i = 0; i < count; i++) {
        img_inode_t *r = &c->inode[i];

        uint32_t uid = img_rd_u32(c->buf + p);
        p += 4;

        int64_t mtime_delta;
        if (img_sleb(c->buf, p, end, &mtime_delta, &used) < 0) {
            return -1;
        }
        p += used;

        uint8_t kind = c->buf[p++];

        r->kind = kind;
        r->uid = uid;
        r->mtime_delta = mtime_delta;
        r->nbytes = 0;
        r->nchild = 0;
        r->child_off = 0;

        if (kind == IMG_FILE) {
            uint64_t nb;
            if (img_uleb(c->buf, p, end, &nb, &used) < 0) {
                return -1;
            }
            p += used;
            r->nbytes = (uint32_t)nb;

            volatile uint32_t sink = 0;
            for (uint64_t j = 0; j < nb; j++) {
                sink += c->buf[p + j];
            }
            (void)sink;
            p += nb;
            c->file_count++;
        } else if (kind == IMG_DIR) {
            uint64_t nm;
            if (img_uleb(c->buf, p, end, &nm, &used) < 0) {
                return -1;
            }
            p += used;
            r->nchild = (uint32_t)nm;
            r->child_off = p;
            for (uint64_t j = 0; j < nm; j++) {
                uint64_t idx;
                if (img_uleb(c->buf, p, end, &idx, &used) < 0) {
                    return -1;
                }
                p += used;
                (void)idx;
            }
            c->dir_count++;
        } else {
            return img_error("inode", "unknown inode kind %u", (unsigned)kind);
        }
    }
    return 0;
}

/* Sums the resident data bytes reachable from an inode: a file inode gives its
 * own resident byte count; a directory inode gives the sum over the inodes it
 * lists as children. */
static long resolve(img_image_t *c, uint64_t idx) {
    img_inode_t *r = &c->inode[idx];
    if (r->kind == IMG_FILE) {
        return r->nbytes;
    }

    size_t end = (size_t)(c->inodes - c->buf) + c->inodes_size;
    size_t p = r->child_off;
    long sum = 0;
    for (uint32_t j = 0; j < r->nchild; j++) {
        uint64_t f;
        size_t used;
        img_uleb(c->buf, p, end, &f, &used);
        p += used;
        sum += resolve(c, f);
    }
    return sum;
}

int img_inode_resolve(img_image_t *c) {
    if (c->inode_count == 0) {
        c->data_bytes = 0;
        return 0;
    }
    c->data_bytes = resolve(c, 0);
    return 0;
}
