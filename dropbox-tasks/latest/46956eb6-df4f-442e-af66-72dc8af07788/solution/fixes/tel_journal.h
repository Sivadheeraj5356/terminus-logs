#ifndef TEL_JOURNAL_H
#define TEL_JOURNAL_H
#include "tel_report.h"
#include <stddef.h>
#include <stdint.h>

typedef struct {
    int lock_fd;
    char path[512];
    uint64_t last_generation;
    uint32_t valid_records;
    uint32_t recovered_records;
    int had_corrupt_tail;
} tel_journal_t;

int tel_journal_open(tel_journal_t *j, const char *state_dir, const char *scenario_id);
void tel_journal_close(tel_journal_t *j);
int tel_journal_fingerprint(const char *db_path, const char *scenario_id, int loops,
                            char out_hex[65]);
int tel_journal_load(tel_journal_t *j, const char fingerprint[65],
                     tel_scenario_report_t *out, int *cache_hit);
int tel_journal_append(tel_journal_t *j, const char fingerprint[65],
                       const tel_scenario_report_t *report);
int tel_journal_compact(tel_journal_t *j);
#endif
