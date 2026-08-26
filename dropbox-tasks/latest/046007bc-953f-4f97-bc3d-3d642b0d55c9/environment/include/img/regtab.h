#ifndef IMG_REGTAB_H
#define IMG_REGTAB_H

#include "img/types.h"

/* Walks the region table and points the image at each region's bytes. */
int img_regtab_parse(img_image_t *c);

#endif
