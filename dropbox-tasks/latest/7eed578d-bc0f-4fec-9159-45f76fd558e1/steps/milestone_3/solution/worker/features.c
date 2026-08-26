#include "features.h"
#include "db.h"

#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

typedef struct {
    char account_id[64];
    int tx_count;
    long total_amount;
    long max_amount;
    int foreign_count;
} AccountAgg;

static int cmp_account(const void *a, const void *b) {
    return strcmp(((const AccountAgg *)a)->account_id, ((const AccountAgg *)b)->account_id);
}

static void utc_now(char *buf, size_t len) {
    time_t now = time(NULL);
    struct tm tm;
    gmtime_r(&now, &tm);
    strftime(buf, len, "%Y-%m-%dT%H:%M:%SZ", &tm);
}

int features_populate(const LedgerBatch *batch, const char *batch_id) {
    AccountAgg *aggs = NULL;
    int agg_count = 0;
    int agg_cap = 0;

    for (int i = 0; i < batch->count; i++) {
        const LedgerRow *row = &batch->rows[i];
        if (row->sequence == 0 || strcmp(row->pan_hash, "GENESIS") == 0) {
            continue;
        }

        int idx = -1;
        for (int j = 0; j < agg_count; j++) {
            if (strcmp(aggs[j].account_id, row->pan_hash) == 0) {
                idx = j;
                break;
            }
        }

        if (idx < 0) {
            if (agg_count >= agg_cap) {
                agg_cap = agg_cap == 0 ? 8 : agg_cap * 2;
                AccountAgg *tmp = realloc(aggs, (size_t)agg_cap * sizeof(AccountAgg));
                if (!tmp) {
                    free(aggs);
                    return -1;
                }
                aggs = tmp;
            }
            idx = agg_count++;
            memset(&aggs[idx], 0, sizeof(aggs[idx]));
            strncpy(aggs[idx].account_id, row->pan_hash, sizeof(aggs[idx].account_id) - 1);
        }

        aggs[idx].tx_count++;
        aggs[idx].total_amount += row->amount_cents;
        if (row->amount_cents > aggs[idx].max_amount) {
            aggs[idx].max_amount = row->amount_cents;
        }
        if (strcmp(row->country, "US") != 0) {
            aggs[idx].foreign_count++;
        }
    }

    if (agg_count == 0) {
        free(aggs);
        return 0;
    }

    qsort(aggs, (size_t)agg_count, sizeof(AccountAgg), cmp_account);

    sqlite3 *db = NULL;
    if (db_open(&db) != 0) {
        free(aggs);
        return -1;
    }

    char ts[32];
    utc_now(ts, sizeof(ts));

    sqlite3_exec(db, "BEGIN;", NULL, NULL, NULL);
    for (int i = 0; i < agg_count; i++) {
        double avg = (double)aggs[i].total_amount / (double)aggs[i].tx_count;
        double foreign_ratio = (double)aggs[i].foreign_count / (double)aggs[i].tx_count;

        char sql[1024];
        snprintf(
            sql,
            sizeof(sql),
            "INSERT OR REPLACE INTO feature_store "
            "(batch_id, account_id, tx_count, total_amount, avg_amount, foreign_ratio, max_amount, populated_at) "
            "VALUES ('%s','%s',%d,%ld,%.6f,%.6f,%ld,'%s');",
            batch_id,
            aggs[i].account_id,
            aggs[i].tx_count,
            aggs[i].total_amount,
            avg,
            foreign_ratio,
            aggs[i].max_amount,
            ts
        );
        if (db_exec(db, sql) != 0) {
            sqlite3_exec(db, "ROLLBACK;", NULL, NULL, NULL);
            sqlite3_close(db);
            free(aggs);
            return -1;
        }
    }
    sqlite3_exec(db, "COMMIT;", NULL, NULL, NULL);
    sqlite3_close(db);
    free(aggs);
    return agg_count;
}
