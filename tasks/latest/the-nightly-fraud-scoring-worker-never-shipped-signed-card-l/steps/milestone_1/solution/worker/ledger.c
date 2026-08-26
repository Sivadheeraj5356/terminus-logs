#include "ledger.h"
#include "hmac.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static char *trim_newline(char *s) {
    size_t n = strlen(s);
    while (n > 0 && (s[n - 1] == '\n' || s[n - 1] == '\r')) {
        s[--n] = '\0';
    }
    return s;
}

const char *ledger_default_path(void) {
    return "/app/data/ledger/batch_001.csv";
}

static int split_csv_line(char *line, char **fields, int max_fields) {
    int count = 0;
    char *cursor = line;
    while (count < max_fields) {
        fields[count++] = cursor;
        char *comma = strchr(cursor, ',');
        if (!comma) {
            break;
        }
        *comma = '\0';
        cursor = comma + 1;
    }
    return count;
}

int ledger_load(const char *path, LedgerBatch *batch) {
    FILE *fp = fopen(path, "r");
    if (!fp) {
        perror("fopen ledger");
        return -1;
    }

    char line[512];
    if (!fgets(line, sizeof(line), fp)) {
        fclose(fp);
        return -1;
    }

    LedgerRow *rows = NULL;
    int cap = 0;
    int count = 0;

    while (fgets(line, sizeof(line), fp)) {
        trim_newline(line);
        if (line[0] == '\0') {
            continue;
        }

        if (count >= cap) {
            cap = cap == 0 ? 16 : cap * 2;
            LedgerRow *tmp = realloc(rows, (size_t)cap * sizeof(LedgerRow));
            if (!tmp) {
                free(rows);
                fclose(fp);
                return -1;
            }
            rows = tmp;
        }

        LedgerRow *row = &rows[count];
        memset(row, 0, sizeof(*row));

        char *fields[7];
        int nfields = split_csv_line(line, fields, 7);
        if (nfields < 7) {
            continue;
        }

        strncpy(row->batch_id, fields[0], sizeof(row->batch_id) - 1);
        row->sequence = atoi(fields[1]);
        strncpy(row->pan_hash, fields[2], sizeof(row->pan_hash) - 1);
        row->amount_cents = atol(fields[3]);
        strncpy(row->merchant_code, fields[4], sizeof(row->merchant_code) - 1);
        strncpy(row->country, fields[5], sizeof(row->country) - 1);
        strncpy(row->hmac, fields[6], sizeof(row->hmac) - 1);

        count++;
    }

    fclose(fp);
    batch->rows = rows;
    batch->count = count;
    return 0;
}

void ledger_free(LedgerBatch *batch) {
    free(batch->rows);
    batch->rows = NULL;
    batch->count = 0;
}

int ledger_verify_chain(
    const LedgerBatch *batch,
    const char *secret,
    const char *cli_batch
) {
    if (batch->count == 0 || cli_batch == NULL || cli_batch[0] == '\0') {
        return -1;
    }

    for (int i = 0; i < batch->count; i++) {
        const LedgerRow *row = &batch->rows[i];
        if (strcmp(row->batch_id, cli_batch) != 0) {
            return -1;
        }
        if (row->sequence != i) {
            return -1;
        }
    }

    const LedgerRow *first = &batch->rows[0];
    if (first->sequence != 0 || strcmp(first->pan_hash, "GENESIS") != 0) {
        return -1;
    }

    char expected[128];
    char message[512];

    snprintf(message, sizeof(message), "GENESIS|%s", cli_batch);
    if (hmac_sha256_hex(secret, message, expected, sizeof(expected)) != 0) {
        return -1;
    }
    if (strcmp(expected, first->hmac) != 0) {
        return -1;
    }

    const char *prev = first->hmac;
    for (int i = 1; i < batch->count; i++) {
        const LedgerRow *row = &batch->rows[i];
        snprintf(
            message,
            sizeof(message),
            "%s|%s|%ld|%s|%s",
            prev,
            row->pan_hash,
            row->amount_cents,
            row->merchant_code,
            row->country
        );
        if (hmac_sha256_hex(secret, message, expected, sizeof(expected)) != 0) {
            return -1;
        }
        if (strcmp(expected, row->hmac) != 0) {
            return -1;
        }
        prev = row->hmac;
    }
    return 0;
}

int ledger_batch_matches_cli(const LedgerBatch *batch, const char *cli_batch) {
    if (cli_batch == NULL || cli_batch[0] == '\0' || batch->count == 0) {
        return -1;
    }
    for (int i = 0; i < batch->count; i++) {
        if (strcmp(batch->rows[i].batch_id, cli_batch) != 0) {
            return -1;
        }
    }
    return 0;
}
