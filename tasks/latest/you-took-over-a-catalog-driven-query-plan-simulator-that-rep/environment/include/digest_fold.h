#ifndef DIGEST_FOLD_H
#define DIGEST_FOLD_H

#include <stddef.h>
#include <stdint.h>

#include "plan_types.h"

void fold_hex(const char *a, const char *b, const char *c, uint32_t gen, char *out, size_t out_len);
void plan_digest_row(const pl_row *row, char *out, size_t out_len);

#endif
