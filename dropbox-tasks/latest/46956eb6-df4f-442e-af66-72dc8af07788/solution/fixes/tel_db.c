#include "tel_db.h"

#include "tel_keys.h"

#include <stdio.h>
#include <string.h>

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
    return 0;
}

void tel_env_close(tel_env_t *db) {
    if (!db || !db->env) {
        return;
    }
    mdb_env_close(db->env);
    db->env = NULL;
}
