#ifndef TEL_DB_H
#define TEL_DB_H

#include <lmdb.h>

typedef struct {
    MDB_env *env;
    MDB_dbi samples;
    MDB_dbi errors;
    MDB_dbi restarts;
} tel_env_t;

int tel_env_open(const char *path, tel_env_t *out);
void tel_env_close(tel_env_t *db);

#endif
