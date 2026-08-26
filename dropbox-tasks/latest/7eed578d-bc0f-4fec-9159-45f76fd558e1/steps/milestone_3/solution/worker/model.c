#include "model.h"
#include "db.h"
#include "hmac.h"

#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

static const double INTERCEPT = -2.5;
static const double W_TX_COUNT = 0.15;
static const double W_TOTAL_AMOUNT = 0.00001;
static const double W_FOREIGN_RATIO = 1.8;
static const double W_MAX_AMOUNT = 0.00005;

static char *read_trimmed_secret(const char *path) {
    FILE *fp = fopen(path, "r");
    if (!fp) {
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

static double sigmoid(double z) {
    return 1.0 / (1.0 + exp(-z));
}

int model_run_scoring(const char *job_id) {
    char *predict_secret = read_trimmed_secret("/app/config/predict_secret.txt");
    if (!predict_secret) {
        return -1;
    }

    sqlite3 *db = NULL;
    if (db_open(&db) != 0) {
        free(predict_secret);
        return -1;
    }

    const char *job_sql =
        "SELECT batch_id FROM scoring_jobs WHERE job_id = ? AND status = 'queued';";
    sqlite3_stmt *job_stmt = NULL;
    if (sqlite3_prepare_v2(db, job_sql, -1, &job_stmt, NULL) != SQLITE_OK) {
        sqlite3_close(db);
        free(predict_secret);
        return -1;
    }
    sqlite3_bind_text(job_stmt, 1, job_id, -1, SQLITE_STATIC);
    if (sqlite3_step(job_stmt) != SQLITE_ROW) {
        sqlite3_finalize(job_stmt);
        sqlite3_close(db);
        free(predict_secret);
        return -1;
    }
    const char *batch_id = (const char *)sqlite3_column_text(job_stmt, 0);
    char batch_copy[64];
    memset(batch_copy, 0, sizeof(batch_copy));
    strncpy(batch_copy, batch_id, sizeof(batch_copy) - 1);
    sqlite3_finalize(job_stmt);

    const char *feat_sql =
        "SELECT account_id, tx_count, total_amount, foreign_ratio, max_amount "
        "FROM feature_store WHERE batch_id = ? ORDER BY account_id;";
    sqlite3_stmt *feat_stmt = NULL;
    if (sqlite3_prepare_v2(db, feat_sql, -1, &feat_stmt, NULL) != SQLITE_OK) {
        sqlite3_close(db);
        free(predict_secret);
        return -1;
    }
    sqlite3_bind_text(feat_stmt, 1, batch_copy, -1, SQLITE_STATIC);

    char ts[32];
    utc_now(ts, sizeof(ts));
    sqlite3_exec(db, "BEGIN;", NULL, NULL, NULL);

    int count = 0;
    while (sqlite3_step(feat_stmt) == SQLITE_ROW) {
        const char *account = (const char *)sqlite3_column_text(feat_stmt, 0);
        int tx_count = sqlite3_column_int(feat_stmt, 1);
        long total_amount = sqlite3_column_int64(feat_stmt, 2);
        double foreign_ratio = sqlite3_column_double(feat_stmt, 3);
        long max_amount = sqlite3_column_int64(feat_stmt, 4);

        double z = INTERCEPT
            + W_TX_COUNT * (double)tx_count
            + W_TOTAL_AMOUNT * (double)total_amount
            + W_FOREIGN_RATIO * foreign_ratio
            + W_MAX_AMOUNT * (double)max_amount;
        double risk = sigmoid(z);

        char score_str[32];
        snprintf(score_str, sizeof(score_str), "%.6f", risk);

        char msg[256];
        snprintf(msg, sizeof(msg), "%s|%s|%s", job_id, account, score_str);
        char hmac_hex[128];
        if (hmac_sha256_hex(predict_secret, msg, hmac_hex, sizeof(hmac_hex)) != 0) {
            sqlite3_finalize(feat_stmt);
            sqlite3_exec(db, "ROLLBACK;", NULL, NULL, NULL);
            sqlite3_close(db);
            free(predict_secret);
            return -1;
        }

        char insert[1024];
        snprintf(
            insert,
            sizeof(insert),
            "INSERT OR REPLACE INTO scoring_predictions "
            "(job_id, account_id, risk_score, prediction_hmac, signed_at) "
            "VALUES ('%s','%s',%s,'%s','%s');",
            job_id,
            account,
            score_str,
            hmac_hex,
            ts
        );
        if (db_exec(db, insert) != 0) {
            sqlite3_finalize(feat_stmt);
            sqlite3_exec(db, "ROLLBACK;", NULL, NULL, NULL);
            sqlite3_close(db);
            free(predict_secret);
            return -1;
        }
        count++;
    }
    sqlite3_finalize(feat_stmt);

    char update[512];
    snprintf(
        update,
        sizeof(update),
        "UPDATE scoring_jobs SET status='completed', completed_at='%s' WHERE job_id='%s';",
        ts,
        job_id
    );
    if (db_exec(db, update) != 0) {
        sqlite3_exec(db, "ROLLBACK;", NULL, NULL, NULL);
        sqlite3_close(db);
        free(predict_secret);
        return -1;
    }

    sqlite3_exec(db, "COMMIT;", NULL, NULL, NULL);
    sqlite3_close(db);
    free(predict_secret);
    return count;
}
