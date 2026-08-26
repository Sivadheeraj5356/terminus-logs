#ifndef IMG_JSON_H
#define IMG_JSON_H

#include <stdio.h>

#include "img/types.h"

/* Writes the one-line JSON summary of a well-formed disk image. */
void img_write_summary(FILE *out, const img_image_t *c);

#endif
