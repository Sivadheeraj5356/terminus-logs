#include "row_fold.h"

#include <stdio.h>

void echo_row(const packed_row *row) {
    if (!row) {
        return;
    }
    fprintf(stderr, "row-echo pane=%s key=%s off=%d\n", row->pane, row->day_key, row->wall_off);
}
