#ifndef IMG_INODE_H
#define IMG_INODE_H

#include "img/types.h"

/* Parses the inode table and resolves the root inode's resident footprint
 * through the directory tree. */
int img_inode_parse(img_image_t *c);
int img_inode_resolve(img_image_t *c);

#endif
