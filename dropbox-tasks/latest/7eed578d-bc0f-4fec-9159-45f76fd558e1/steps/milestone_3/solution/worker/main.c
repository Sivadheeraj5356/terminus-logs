#include "db.h"
#include "features.h"
#include "ledger.h"
#include "model.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

static char *read_trimmed_secret(const char *path) {
    FILE *fp = fopen(path, "r");
    if (!fp) {
        perror(path);
        return NULL;
    }
    char buf[256];
    if (!fgets(buf, sizeof(buf), fp)) {
        fclose(fp);
        return NULL;
    }
    fclose(fp);
    size_t n = strlen(buf);
    while (n > 0 && (buf[n - 1] == '\n' || buf[n - 1] == '\r' || buf[n - 1] == ' ')) {
        buf[--n] = '\0';
    }
    return strdup(buf);
}

static void utc_now(char *buf, size_t len) {
    time_t now = time(NULL);
    struct tm tm;
    gmtime_r(&now, &tm);
    strftime(buf, len, "%Y-%m-%dT%H:%M:%SZ", &tm);
}

static int cmd_verify_ledger(int argc, char **argv) {
    const char *batch = "BATCH-001";
    const char *ledger = ledger_default_path();

    for (int i = 2; i < argc; i++) {
        if (strcmp(argv[i], "--batch") == 0 && i + 1 < argc) {
            batch = argv[++i];
        } else if (strcmp(argv[i], "--ledger") == 0 && i + 1 < argc) {
            ledger = argv[++i];
        }
    }

    char *secret = read_trimmed_secret("/app/config/hmac_secret.txt");
    if (!secret) {
        return 1;
    }

    LedgerBatch loaded = {0};
    if (ledger_load(ledger, &loaded) != 0) {
        free(secret);
        return 1;
    }

    if (ledger_verify_chain(&loaded, secret, batch) != 0) {
        ledger_free(&loaded);
        free(secret);
        fprintf(stderr, "HMAC chain verification failed\n");
        return 1;
    }

    sqlite3 *db = NULL;
    if (db_open(&db) != 0) {
        ledger_free(&loaded);
        free(secret);
        return 1;
    }

    char ts[32];
    utc_now(ts, sizeof(ts));
    char sql[512];
    snprintf(
        sql,
        sizeof(sql),
        "INSERT OR REPLACE INTO ledger_verifications "
        "(batch_id, row_count, chain_ok, verified_at) VALUES ('%s', %d, 1, '%s');",
        batch,
        loaded.count,
        ts
    );
    if (db_exec(db, sql) != 0) {
        sqlite3_close(db);
        ledger_free(&loaded);
        free(secret);
        return 1;
    }
    sqlite3_close(db);

    printf("VERIFY batch=%s rows=%d chain=OK\n", batch, loaded.count);
    ledger_free(&loaded);
    free(secret);
    return 0;
}

static int cmd_populate_features(int argc, char **argv) {
    const char *batch = "BATCH-001";
    const char *ledger = ledger_default_path();
    for (int i = 2; i < argc; i++) {
        if (strcmp(argv[i], "--batch") == 0 && i + 1 < argc) {
            batch = argv[++i];
        } else if (strcmp(argv[i], "--ledger") == 0 && i + 1 < argc) {
            ledger = argv[++i];
        }
    }

    sqlite3 *db = NULL;
    if (db_open(&db) != 0) {
        return 1;
    }
    sqlite3_stmt *stmt = NULL;
    const char *check =
        "SELECT chain_ok FROM ledger_verifications WHERE batch_id = ?;";
    if (sqlite3_prepare_v2(db, check, -1, &stmt, NULL) != SQLITE_OK) {
        sqlite3_close(db);
        return 1;
    }
    sqlite3_bind_text(stmt, 1, batch, -1, SQLITE_STATIC);
    if (sqlite3_step(stmt) != SQLITE_ROW || sqlite3_column_int(stmt, 0) != 1) {
        sqlite3_finalize(stmt);
        sqlite3_close(db);
        fprintf(stderr, "batch not verified\n");
        return 1;
    }
    sqlite3_finalize(stmt);
    sqlite3_close(db);

    LedgerBatch loaded = {0};
    if (ledger_load(ledger, &loaded) != 0) {
        return 1;
    }
    if (ledger_batch_matches_cli(&loaded, batch) != 0) {
        ledger_free(&loaded);
        fprintf(stderr, "ledger batch_id mismatch\n");
        return 1;
    }

    int accounts = features_populate(&loaded, batch);
    ledger_free(&loaded);
    if (accounts < 0) {
        return 1;
    }

    printf("FEATURES batch=%s accounts=%d\n", batch, accounts);
    return 0;
}

static int cmd_run_scoring(int argc, char **argv) {
    const char *job = NULL;
    for (int i = 2; i < argc; i++) {
        if (strcmp(argv[i], "--job") == 0 && i + 1 < argc) {
            job = argv[++i];
        }
    }
    if (!job) {
        fprintf(stderr, "missing --job\n");
        return 1;
    }

    int accounts = model_run_scoring(job);
    if (accounts < 0) {
        return 1;
    }

    printf("SCORE job=%s accounts=%d status=completed\n", job, accounts);
    return 0;
}

static void usage(const char *prog) {
    fprintf(
        stderr,
        "usage: %s verify-ledger [--batch ID] [--ledger PATH]\n"
        "       %s populate-features [--batch ID] [--ledger PATH]\n"
        "       %s run-scoring --job ID\n",
        prog,
        prog,
        prog
    );
}

int main(int argc, char **argv) {
    if (argc < 2) {
        usage(argv[0]);
        return 1;
    }

    if (strcmp(argv[1], "verify-ledger") == 0) {
        return cmd_verify_ledger(argc, argv);
    }
    if (strcmp(argv[1], "populate-features") == 0) {
        return cmd_populate_features(argc, argv);
    }
    if (strcmp(argv[1], "run-scoring") == 0) {
        return cmd_run_scoring(argc, argv);
    }

    usage(argv[0]);
    return 1;
}
