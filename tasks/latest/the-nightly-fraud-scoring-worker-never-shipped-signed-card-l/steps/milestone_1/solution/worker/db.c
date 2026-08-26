#include "db.h"

#include <stdio.h>
#include <string.h>

int db_open(sqlite3 **db) {
    int rc = sqlite3_open(DB_PATH, db);
    if (rc != SQLITE_OK) {
        if (*db != NULL) {
            fprintf(stderr, "db open failed: %s\n", sqlite3_errmsg(*db));
            sqlite3_close(*db);
            *db = NULL;
        } else {
            fprintf(stderr, "db open failed: rc=%d\n", rc);
        }
        return -1;
    }
    sqlite3_exec(*db, "PRAGMA foreign_keys = ON;", NULL, NULL, NULL);
    return 0;
}

int db_exec(sqlite3 *db, const char *sql) {
    char *err = NULL;
    int rc = sqlite3_exec(db, sql, NULL, NULL, &err);
    if (rc != SQLITE_OK) {
        fprintf(stderr, "sql error: %s\n", err ? err : sqlite3_errmsg(db));
        sqlite3_free(err);
        return -1;
    }
    return 0;
}
