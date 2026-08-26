#include "dyeworks/str.h"

#include "dyeworks/error.h"

/* Resolve a str-form offset against the strings section. The offset selects a
 * NUL-terminated string; the value occupies no node bytes beyond the offset
 * itself. */
int str_check(dyeworks_t *sp, uint32_t off) {
    const uint8_t *b = sp->buf;
    size_t sbase = sp->sec[DYEWORKS_SEC_STR].off;
    size_t s = sbase + off;

    while (b[s] != 0) {
        s++;
    }

    return 0;
}
