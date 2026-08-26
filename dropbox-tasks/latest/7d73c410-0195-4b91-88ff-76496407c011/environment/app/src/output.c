#include "output.h"

#include <sqlite3.h>
#include <stdio.h>
#include <stdlib.h>

int write_events_json(const char *path, const RecoveryResult *result) {
    FILE *f = fopen(path, "w");
    if (!f) return -1;

    fprintf(f, "{\n  \"events\": [\n");
    for (size_t i = 0; i < result->count; i++) {
        const RecoveredEvent *e = &result->events[i];
        fprintf(
            f,
            "    {\"event_id\":\"%s\",\"f0_hz\":%.9f,\"chirp_hz_per_s\":%.9f,"
            "\"start_s\":%.9f,\"end_s\":%.9f,\"relative_power\":%.9f,\"support\":%d}%s\n",
            e->event_id,
            e->f0_hz,
            e->chirp_hz_per_s,
            e->start_s,
            e->end_s,
            e->relative_power,
            e->support,
            i + 1 == result->count ? "" : ","
        );
    }
    fprintf(f, "  ]\n}\n");
    fclose(f);
    return 0;
}

int write_events_sqlite(const char *path, const RecoveryResult *result) {
    sqlite3 *db = NULL;
    sqlite3_stmt *stmt = NULL;
    if (sqlite3_open(path, &db) != SQLITE_OK) return -1;

    const char *ddl =
        "DROP TABLE IF EXISTS events;"
        "CREATE TABLE events ("
        "event_id TEXT PRIMARY KEY,"
        "f0_hz REAL NOT NULL,"
        "chirp_hz_per_s REAL NOT NULL,"
        "start_s REAL NOT NULL,"
        "end_s REAL NOT NULL,"
        "relative_power REAL NOT NULL,"
        "support INTEGER NOT NULL"
        ");";
    if (sqlite3_exec(db, ddl, NULL, NULL, NULL) != SQLITE_OK) goto fail;

    const char *sql =
        "INSERT INTO events(event_id, f0_hz, chirp_hz_per_s, start_s, end_s, relative_power, support) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)";
    if (sqlite3_prepare_v2(db, sql, -1, &stmt, NULL) != SQLITE_OK) goto fail;

    for (size_t i = 0; i < result->count; i++) {
        const RecoveredEvent *e = &result->events[i];
        sqlite3_bind_text(stmt, 1, e->event_id, -1, SQLITE_STATIC);
        sqlite3_bind_double(stmt, 2, e->f0_hz);
        sqlite3_bind_double(stmt, 3, e->chirp_hz_per_s);
        sqlite3_bind_double(stmt, 4, e->start_s);
        sqlite3_bind_double(stmt, 5, e->end_s);
        sqlite3_bind_double(stmt, 6, e->relative_power);
        sqlite3_bind_int(stmt, 7, e->support);
        if (sqlite3_step(stmt) != SQLITE_DONE) goto fail;
        sqlite3_reset(stmt);
        sqlite3_clear_bindings(stmt);
    }

    sqlite3_finalize(stmt);
    sqlite3_close(db);
    return 0;

fail:
    if (stmt) sqlite3_finalize(stmt);
    sqlite3_close(db);
    return -1;
}
