#include "dyeworks/reader.h"

#include <stdio.h>
#include <stdlib.h>

#include "dyeworks/error.h"

#define DYEWORKS_MAX_FILE (64u * 1024u * 1024u)

int dyeworks_load_file(const char *path, uint8_t **buf, size_t *n) {
    FILE *f = fopen(path, "rb");
    if (!f) {
        return dyeworks_error("format", "cannot open input file");
    }
    if (fseek(f, 0, SEEK_END) != 0) {
        fclose(f);
        return dyeworks_error("format", "cannot seek input file");
    }
    long sz = ftell(f);
    if (sz < 0) {
        fclose(f);
        return dyeworks_error("format", "cannot size input file");
    }
    if (sz == 0) {
        fclose(f);
        return dyeworks_error("format", "empty input file");
    }
    if ((unsigned long)sz > DYEWORKS_MAX_FILE) {
        fclose(f);
        return dyeworks_error("format", "input file too large");
    }
    rewind(f);
    uint8_t *data = malloc((size_t)sz);
    if (!data) {
        fclose(f);
        return dyeworks_error("format", "cannot allocate file buffer");
    }
    if (fread(data, 1, (size_t)sz, f) != (size_t)sz) {
        free(data);
        fclose(f);
        return dyeworks_error("format", "short read on input file");
    }
    fclose(f);
    *buf = data;
    *n = (size_t)sz;
    return 0;
}
