#include "tel_scan.h"

#include "tel_keys.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static char *val_dup(const MDB_val *val) {
    char *out = malloc(val->mv_size + 1);
    if (!out) {
        return NULL;
    }
    memcpy(out, val->mv_data, val->mv_size);
    out[val->mv_size] = '\0';
    return out;
}

static int parse_restart_ts(const char *json, uint64_t *out) {
    const char *p = strstr(json, "\"restart_ts\":");
    if (!p) {
        return -1;
    }
    p += 13;
    *out = strtoull(p, NULL, 10);
    return 0;
}

int tel_scan_samples_once(const tel_env_t *db, int *count_out) {
    MDB_txn *txn = NULL;
    if (mdb_txn_begin(db->env, NULL, MDB_RDONLY, &txn) != 0) {
        return -1;
    }
    MDB_cursor *cur = NULL;
    if (mdb_cursor_open(txn, db->samples, &cur) != 0) {
        mdb_txn_abort(txn);
        return -1;
    }
    int count = 0;
    MDB_val key, val;
    while (mdb_cursor_get(cur, &key, &val, MDB_NEXT) == 0) {
        if (key.mv_size != TEL_SAMPLE_KEY_LEN) {
            continue;
        }
        count++;
    }
    mdb_cursor_close(cur);
    mdb_txn_abort(txn);
    *count_out = count;
    return 0;
}

int tel_walk_restarts_once(const tel_env_t *db, tel_restart_row_t **rows_out, size_t *len_out) {
    MDB_txn *txn = NULL;
    if (mdb_txn_begin(db->env, NULL, MDB_RDONLY, &txn) != 0) {
        return -1;
    }
    tel_restart_row_t *rows = NULL;
    size_t cap = 0;
    size_t len = 0;
    MDB_cursor *cur = NULL;
    if (mdb_cursor_open(txn, db->restarts, &cur) != 0) {
        mdb_txn_abort(txn);
        return -1;
    }
    MDB_val key, val;
    int rc = mdb_cursor_get(cur, &key, &val, MDB_FIRST);
    while (rc == 0) {
        if (key.mv_size == TEL_RESTART_KEY_LEN) {
            if (len >= cap) {
                cap = cap ? cap * 2 : 8;
                rows = realloc(rows, cap * sizeof(*rows));
            }
            rows[len].pid = tel_read_u64_be((const uint8_t *)key.mv_data);
            char *json = val_dup(&val);
            if (json && parse_restart_ts(json, &rows[len].restart_ts) != 0) {
                rows[len].restart_ts = 0;
            }
            free(json);
            len++;
        }
        rc = mdb_cursor_get(cur, &key, &val, MDB_NEXT);
    }
    mdb_cursor_close(cur);
    mdb_txn_abort(txn);
    *rows_out = rows;
    *len_out = len;
    return 0;
}
