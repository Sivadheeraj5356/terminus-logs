#include "img/error.h"

#include <stdarg.h>
#include <stdio.h>

int img_error(const char *subsystem, const char *fmt, ...) {
    va_list ap;
    fprintf(stderr, "imgscan: %s: ", subsystem);
    va_start(ap, fmt);
    vfprintf(stderr, fmt, ap);
    va_end(ap);
    fputc('\n', stderr);
    return -1;
}
