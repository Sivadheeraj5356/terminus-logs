#ifndef TEL_SCAN_H
#define TEL_SCAN_H

#include "tel_db.h"

#include <stddef.h>
#include <stdint.h>

typedef struct {
    uint64_t pid;
    uint64_t restart_ts;
} tel_restart_row_t;

int tel_scan_samples_once(const tel_env_t *db, int *count_out);
int tel_walk_restarts_once(const tel_env_t *db, tel_restart_row_t **rows_out, size_t *len_out);

#endif
