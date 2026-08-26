#ifndef IMG_SUPER_H
#define IMG_SUPER_H

#include "img/types.h"

/* Parses the superblock: magic, version, and region count. */
int img_super_parse(img_image_t *c);

#endif
