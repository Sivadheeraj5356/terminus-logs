#ifndef DYEWORKS_FORM_H
#define DYEWORKS_FORM_H

#include "dyeworks/types.h"

/* Consume one param value of the given form starting at buf[p], advancing *p
 * past it. Returns 0 on success or -1 if the value runs outside the node unit,
 * a referenced string lies outside the strings section, or a lot-ref lies
 * outside the lots table. */
int form_consume(dyeworks_t *sp, uint64_t form, size_t *p, size_t unit_end);
#endif
