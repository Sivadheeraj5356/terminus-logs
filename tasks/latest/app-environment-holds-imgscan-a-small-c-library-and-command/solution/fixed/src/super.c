#include "img/super.h"

#include <string.h>

#include "img/error.h"

/* The image begins with a four-byte magic, a version byte, a region count, and
 * two reserved bytes. The region table follows, one nine-byte entry per
 * region. */
#define IMG_MAGIC "DFIM"
#define IMG_SUPER_SIZE 8
#define IMG_REGENT 9
#define IMG_MIN_VERSION 1
#define IMG_MAX_VERSION 2

int img_super_parse(img_image_t *c) {
    if (c->n < IMG_SUPER_SIZE) {
        return img_error("super", "file shorter than superblock");
    }
    if (memcmp(c->buf, IMG_MAGIC, 4) != 0) {
        return img_error("super", "bad magic");
    }
    uint8_t version = c->buf[4];
    if (version < IMG_MIN_VERSION || version > IMG_MAX_VERSION) {
        return img_error("super", "unsupported version %u", (unsigned)version);
    }

    uint8_t region_count = c->buf[5];
    if ((size_t)IMG_SUPER_SIZE + (size_t)region_count * IMG_REGENT > c->n) {
        return img_error("super", "region table runs past end of file");
    }

    c->version = version;
    c->region_count = region_count;
    return 0;
}
