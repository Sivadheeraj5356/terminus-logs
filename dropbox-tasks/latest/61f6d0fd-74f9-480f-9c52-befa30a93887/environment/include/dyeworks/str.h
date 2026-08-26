#ifndef DYEWORKS_STR_H
#define DYEWORKS_STR_H

#include "dyeworks/types.h"

/* Validate that a str-form offset names a NUL-terminated string inside the
 * strings section. Returns 0 on success or -1 on a clean rejection. */
int str_check(dyeworks_t *sp, uint32_t off);
#endif
