#ifndef ROW_FOLD_H
#define ROW_FOLD_H

#include <stddef.h>

typedef struct {
    int cyc;
    char pane[16];
    char day_key[16];
    int wall_off;
    int seq;
    int payload;
} packed_row;

int fold_row(const char *day_key, int wall_off, int seq, int payload, packed_row *out);
int hash_rows(const packed_row *rows, int count, char *hex_out, size_t hex_cap);

#endif
