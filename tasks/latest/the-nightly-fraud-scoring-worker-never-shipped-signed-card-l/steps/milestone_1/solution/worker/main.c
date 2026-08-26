#include "db.h"
#include "ledger.h"

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

static void usage(const char *prog) {
    fprintf(
        stderr,
        "usage: %s verify-ledger [--batch ID] [--ledger PATH]\n",
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

    usage(argv[0]);
    return 1;
}
