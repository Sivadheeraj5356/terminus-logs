#include "tel_correlate.h"

#include "tel_config.h"
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

static int pid_in_list(uint64_t pid, const uint64_t *list, size_t len) {
    for (size_t i = 0; i < len; i++) {
        if (list[i] == pid) {
            return 1;
        }
    }
    return 0;
}

static int append_pid(uint64_t pid, uint64_t **list, size_t *len, size_t *cap) {
    if (pid_in_list(pid, *list, *len)) {
        return 0;
    }
    if (*len >= *cap) {
        *cap = *cap ? *cap * 2 : 4;
        *list = realloc(*list, (*cap) * sizeof(uint64_t));
    }
    (*list)[(*len)++] = pid;
    return 0;
}

static int cmp_u64(const void *a, const void *b) {
    const uint64_t av = *(const uint64_t *)a;
    const uint64_t bv = *(const uint64_t *)b;
    return (av > bv) - (av < bv);
}

static int parse_error_pid(const char *json, uint64_t *pid_out) {
    const char *p = strstr(json, "\"pid\":");
    if (!p) {
        return -1;
    }
    p += 6;
    *pid_out = strtoull(p, NULL, 10);
    return 0;
}

static int close_error_cursor(MDB_cursor *cur, MDB_txn *txn) {
    if (cur) {
        mdb_cursor_close(cur);
    }
    if (txn) {
        mdb_txn_abort(txn);
    }
    return 0;
}

int tel_correlate_errors_once(const tel_env_t *db, int *count_out) {
    MDB_txn *txn = NULL;
    if (mdb_txn_begin(db->env, NULL, MDB_RDONLY, &txn) != 0) {
        return -1;
    }
    MDB_cursor *cur = NULL;
    if (mdb_cursor_open(txn, db->errors, &cur) != 0) {
        mdb_txn_abort(txn);
        return -1;
    }
    int count = 0;
    MDB_val key, val;
    int rc = mdb_cursor_get(cur, &key, &val, MDB_FIRST);
    while (rc == 0) {
        count++;
        rc = mdb_cursor_get(cur, &key, &val, MDB_NEXT);
    }
    close_error_cursor(cur, txn);
    *count_out = count;
    return 0;
}

int tel_compute_correlation(const tel_env_t *db, const char *scenario_id,
                            tel_restart_row_t *restarts, size_t restart_len,
                            tel_replay_stats_t *stats) {
    stats->restarts_seen = (int)restart_len;
    uint64_t window_ns = tel_config_window_ns(scenario_id);

    MDB_txn *txn = NULL;
    if (mdb_txn_begin(db->env, NULL, MDB_RDONLY, &txn) != 0) {
        return -1;
    }

    size_t pid_cap = 4;
    stats->affected_pids = calloc(pid_cap, sizeof(uint64_t));

    for (size_t i = 0; i < restart_len; i++) {
        uint64_t pid = restarts[i].pid;
        uint64_t R = restarts[i].restart_ts;

        MDB_cursor *cur = NULL;
        if (mdb_cursor_open(txn, db->errors, &cur) != 0) {
            continue;
        }
        MDB_val key, val;
        int rc = mdb_cursor_get(cur, &key, &val, MDB_FIRST);
        while (rc == 0) {
            if (key.mv_size == TEL_ERROR_KEY_LEN) {
                const uint8_t *kb = (const uint8_t *)key.mv_data;
                uint64_t E = tel_read_error_ts_key(kb);
                char *json = val_dup(&val);
                uint64_t err_pid = 0;
                if (json) {
                    parse_error_pid(json, &err_pid);
                }
                if (json && err_pid == pid && E <= R && R - E <= window_ns) {
                    stats->correlated_triples++;
                    append_pid(pid, &stats->affected_pids, &stats->affected_pids_len, &pid_cap);
                }
                free(json);
            }
            rc = mdb_cursor_get(cur, &key, &val, MDB_NEXT);
        }
        mdb_cursor_close(cur);
    }

    mdb_txn_abort(txn);

    if (stats->affected_pids_len > 1) {
        qsort(stats->affected_pids, stats->affected_pids_len, sizeof(uint64_t), cmp_u64);
    }
    return 0;
}
