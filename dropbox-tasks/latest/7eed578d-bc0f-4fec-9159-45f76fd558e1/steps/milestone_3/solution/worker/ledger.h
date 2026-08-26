#ifndef LEDGER_H
#define LEDGER_H

typedef struct {
    char batch_id[64];
    int sequence;
    char pan_hash[64];
    long amount_cents;
    char merchant_code[16];
    char country[8];
    char hmac[128];
} LedgerRow;

typedef struct {
    LedgerRow *rows;
    int count;
} LedgerBatch;

int ledger_load(const char *path, LedgerBatch *batch);
void ledger_free(LedgerBatch *batch);
int ledger_verify_chain(
    const LedgerBatch *batch,
    const char *secret,
    const char *cli_batch
);
int ledger_batch_matches_cli(const LedgerBatch *batch, const char *cli_batch);
const char *ledger_default_path(void);

#endif
