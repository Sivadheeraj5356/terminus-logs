#include "dyeworks/str.h"

#include "dyeworks/error.h"

/* Resolve a str-form offset against the strings section. The offset selects a
 * NUL-terminated string; the value occupies no node bytes beyond the offset
 * itself. The offset and the walk to the terminator are bounded against the
 * strings section. */
int str_check(dyeworks_t *sp, uint32_t off) {
    const uint8_t *b = sp->buf;
    size_t sbase = sp->sec[DYEWORKS_SEC_STR].off;
    size_t ssize = sp->sec[DYEWORKS_SEC_STR].size;

    if (off >= ssize) {
        return dyeworks_error("str", "string offset %u past strings section",
                           (unsigned)off);
    }
    size_t s = off;
    while (s < ssize && b[sbase + s] != 0) {
        s++;
    }
    if (s >= ssize) {
        return dyeworks_error("str", "unterminated string in strings section");
    }

    return 0;
}
