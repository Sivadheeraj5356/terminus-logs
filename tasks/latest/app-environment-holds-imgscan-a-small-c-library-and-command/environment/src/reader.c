#include "img/reader.h"

#include <stdio.h>
#include <stdlib.h>

#include "img/error.h"

int img_load_file(const char *path, uint8_t **buf, size_t *len) {
    FILE *f = fopen(path, "rb");
    if (!f) {
        return img_error("super", "cannot open %s", path);
    }
    if (fseek(f, 0, SEEK_END) != 0) {
        fclose(f);
        return img_error("super", "cannot seek %s", path);
    }
    long size = ftell(f);
    if (size < 0) {
        fclose(f);
        return img_error("super", "cannot size %s", path);
    }
    rewind(f);

    uint8_t *p = malloc((size_t)size ? (size_t)size : 1);
    if (!p) {
        fclose(f);
        return img_error("super", "out of memory");
    }
    if (size > 0 && fread(p, 1, (size_t)size, f) != (size_t)size) {
        free(p);
        fclose(f);
        return img_error("super", "short read on %s", path);
    }
    fclose(f);

    *buf = p;
    *len = (size_t)size;
    return 0;
}
