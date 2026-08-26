#include "img/inode.h"

#include <stdlib.h>

#include "img/bytes.h"
#include "img/error.h"
#include "img/varint.h"

#define IMG_MAX_DEPTH 256 /* far deeper than any real directory tree, shallow
                           * enough to keep the resolver recursion off the stack
                           * edge on a linear chain */

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

    /* Each inode is at least six bytes, so a plausible count can never exceed
     * the region size; this also bounds the allocation. */
    if (count > c->inodes_size) {
        return img_error("inode", "inode count exceeds region size");
    }
    size_t nalloc = (size_t)count * sizeof(img_inode_t);
    c->inode = malloc(nalloc ? nalloc : 1);
    if (!c->inode) {
        return img_error("inode", "out of memory");
    }
    c->inode_count = count;

    for (uint64_t i = 0; i < count; i++) {
        img_inode_t *r = &c->inode[i];

        if (p + 4 > end) {
            return img_error("inode", "uid past region");
        }
        uint32_t uid = img_rd_u32(c->buf + p);
        p += 4;

        int64_t mtime_delta;
        if (img_sleb(c->buf, p, end, &mtime_delta, &used) < 0) {
            return -1;
        }
        p += used;

        if (p >= end) {
            return img_error("inode", "inode kind past region");
        }
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
            if (nb > end - p) {
                return img_error("data", "resident run past region");
            }
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

/* Sums the resident data bytes reachable from an inode. A file inode gives its
 * own resident byte count; a directory inode gives the sum, with multiplicity,
 * over the inodes it lists as children. Each inode's footprint is settled once
 * and reused, so a directory that lists the same subtree many times, or that is
 * itself listed by many directories, is summed without re-walking the shared
 * part every time it is named. The child index is bounded, a directory found on
 * the current path is a cycle and rejected, and the nesting depth is capped so a
 * hostile chain cannot run off the array or the stack. state: 0 unseen, 1 on the
 * current path, 2 settled. */
static int resolve(img_image_t *c, uint64_t idx, int depth, long *out,
                   long *foot, unsigned char *state) {
    if (idx >= c->inode_count) {
        return img_error("child", "child index out of range");
    }
    if (state[idx] == 2) {
        *out = foot[idx];
        return 0;
    }
    if (state[idx] == 1) {
        return img_error("child", "directory cycle");
    }
    if (depth > IMG_MAX_DEPTH) {
        return img_error("child", "directory nesting too deep");
    }
    img_inode_t *r = &c->inode[idx];
    if (r->kind == IMG_FILE) {
        foot[idx] = r->nbytes;
        state[idx] = 2;
        *out = r->nbytes;
        return 0;
    }

    state[idx] = 1;
    size_t end = (size_t)(c->inodes - c->buf) + c->inodes_size;
    size_t p = r->child_off;
    long sum = 0;
    for (uint32_t j = 0; j < r->nchild; j++) {
        uint64_t f;
        size_t used;
        if (img_uleb(c->buf, p, end, &f, &used) < 0) {
            return -1;
        }
        p += used;
        long part;
        if (resolve(c, f, depth + 1, &part, foot, state) < 0) {
            return -1;
        }
        sum += part;
    }
    foot[idx] = sum;
    state[idx] = 2;
    *out = sum;
    return 0;
}

int img_inode_resolve(img_image_t *c) {
    if (c->inode_count == 0) {
        c->data_bytes = 0;
        return 0;
    }
    long *foot = calloc(c->inode_count, sizeof(long));
    unsigned char *state = calloc(c->inode_count, 1);
    if (!foot || !state) {
        free(foot);
        free(state);
        return img_error("child", "out of memory");
    }
    long out;
    int rc = resolve(c, 0, 0, &out, foot, state);
    free(foot);
    free(state);
    if (rc < 0) {
        return -1;
    }
    c->data_bytes = out;
    return 0;
}
