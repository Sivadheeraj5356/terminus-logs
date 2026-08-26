#ifndef DB_H
#define DB_H

#include <sqlite3.h>

#define DB_PATH "/var/lib/ops/ops.db"

int db_open(sqlite3 **db);
int db_exec(sqlite3 *db, const char *sql);

#endif
