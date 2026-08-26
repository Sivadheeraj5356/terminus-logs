#ifndef IMG_VOL_H
#define IMG_VOL_H

#include "img/types.h"

/* Parses the volume descriptor table and validates each volume label. */
int img_vol_parse(img_image_t *c);

#endif
