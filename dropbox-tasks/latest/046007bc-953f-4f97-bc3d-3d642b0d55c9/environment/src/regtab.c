#include "img/regtab.h"

#include "img/bytes.h"
#include "img/error.h"

#define IMG_SUPER_SIZE 8
#define IMG_REGENT 9

#define IMG_REG_NAMES 0
#define IMG_REG_VOLUMES 1
#define IMG_REG_INODES 2
#define IMG_REG_LINKS 3
#define IMG_REG_XATTRS 4

/* Walks the region table, one nine-byte entry (kind, offset, size) per region,
 * and points the image at each region's bytes inside the file. */
int img_regtab_parse(img_image_t *c) {
    for (unsigned i = 0; i < c->region_count; i++) {
        const uint8_t *e = c->buf + IMG_SUPER_SIZE + (size_t)i * IMG_REGENT;
        uint8_t kind = e[0];
        uint32_t off = img_rd_u32(e + 1);
        uint32_t size = img_rd_u32(e + 5);

        const uint8_t *base = c->buf + off;
        switch (kind) {
        case IMG_REG_NAMES:
            c->names = base;
            c->names_size = size;
            break;
        case IMG_REG_VOLUMES:
            c->volumes = base;
            c->volumes_size = size;
            break;
        case IMG_REG_INODES:
            c->inodes = base;
            c->inodes_size = size;
            break;
        case IMG_REG_LINKS:
            c->links = base;
            c->links_size = size;
            break;
        case IMG_REG_XATTRS:
            c->xattrs = base;
            c->xattrs_size = size;
            break;
        default:
            break;
        }
    }

    if (c->inodes == 0) {
        return img_error("regtab", "no inodes region");
    }
    return 0;
}
