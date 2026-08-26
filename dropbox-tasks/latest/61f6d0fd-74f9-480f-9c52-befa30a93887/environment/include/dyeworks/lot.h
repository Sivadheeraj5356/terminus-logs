#ifndef DYEWORKS_LOT_H
#define DYEWORKS_LOT_H

#include "dyeworks/types.h"

/* Resolve a lot-ref index against the lots table. Returns 0 on success or -1
 * on a clean rejection when the index lies outside the table. */
int lot_check(dyeworks_t *sp, uint32_t index);
#endif
