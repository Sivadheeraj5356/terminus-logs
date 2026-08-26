#ifndef TOFLAB_REPORT_H
#define TOFLAB_REPORT_H

#include "reconcile.h"

#include <stddef.h>

/* Validate schema file bytes/marker and compute digest. Returns 0 on success. */
int schema_bind(const char *schema_path, char *digest_out, size_t digest_cap);

/* Atomically write report. Returns 0 on success. */
int write_report(const char *out_path, const char *api_base, const char *run_id,
                 const char *schema_digest, const ReconcileResult *result,
                 char *ledger_digest_out, size_t digest_cap);

#endif
