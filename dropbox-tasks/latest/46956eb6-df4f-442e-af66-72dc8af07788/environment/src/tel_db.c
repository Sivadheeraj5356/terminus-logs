#include "tel_db.h"

#include "tel_keys.h"

#include <stdio.h>
#include <string.h>

static void tel_validate_samples_cache(tel_env_t *out) {
    MDB_txn *txn = NULL;
    if (mdb_txn_begin(out->env, NULL, MDB_RDONLY, &txn) != 0) {
        return;
    }
    MDB_cursor *cur = NULL;
    if (mdb_cursor_open(txn, out->samples, &cur) != 0) {
        mdb_txn_abort(txn);
        return;
    }
    MDB_val key, val;
    if (mdb_cursor_get(cur, &key, &val, MDB_FIRST) != 0) {
        mdb_cursor_close(cur);
        mdb_txn_abort(txn);
    }
}

int tel_env_open(const char *path, tel_env_t *out) {
    memset(out, 0, sizeof(*out));
    int rc = mdb_env_create(&out->env);
    if (rc != 0) {
        return -1;
    }
    rc = mdb_env_set_maxdbs(out->env, 8);
    if (rc != 0) {
        mdb_env_close(out->env);
        return -1;
    }
    rc = mdb_env_open(out->env, path, MDB_RDONLY, 0644);
    if (rc != 0) {
        mdb_env_close(out->env);
        return -1;
    }
    MDB_txn *txn = NULL;
    rc = mdb_txn_begin(out->env, NULL, MDB_RDONLY, &txn);
    if (rc != 0) {
        mdb_env_close(out->env);
        return -1;
    }
    rc = mdb_dbi_open(txn, TEL_SAMPLES_DBI, 0, &out->samples);
    if (rc != 0) {
        mdb_txn_abort(txn);
        mdb_env_close(out->env);
        return -1;
    }
    rc = mdb_dbi_open(txn, TEL_ERRORS_DBI, 0, &out->errors);
    if (rc != 0) {
        mdb_txn_abort(txn);
        mdb_env_close(out->env);
        return -1;
    }
    rc = mdb_dbi_open(txn, TEL_RESTARTS_DBI, 0, &out->restarts);
    if (rc != 0) {
        mdb_txn_abort(txn);
        mdb_env_close(out->env);
        return -1;
    }
    mdb_txn_commit(txn);
    tel_validate_samples_cache(out);
    return 0;
}

void tel_env_close(tel_env_t *db) {
    if (!db || !db->env) {
        return;
    }
    mdb_env_close(db->env);
    db->env = NULL;
}
