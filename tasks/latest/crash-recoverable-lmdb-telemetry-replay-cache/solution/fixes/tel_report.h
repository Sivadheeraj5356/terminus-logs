#ifndef TEL_REPORT_H
#define TEL_REPORT_H
#include <stddef.h>
#include <stdint.h>
typedef struct {
    char scenario_id[64];
    int schema_version;
    int loops_run;
    int initial_open_fds;
    int final_open_fds;
    int fd_delta;
    int leak_reproduced;
    char root_cause[32];
    uint64_t *affected_pids;
    size_t affected_pids_len;
    int samples_scanned;
    int errors_seen;
    int restarts_seen;
    int correlated_triples;
    char body_sha256[65];
    uint64_t generation;
    uint32_t recovered_records;
    int cache_hit;
    char input_fingerprint[65];
    uint64_t journal_bytes;
} tel_scenario_report_t;
typedef struct { int schema_version; tel_scenario_report_t *scenarios; size_t scenario_count; char matrix_digest[65]; } tel_matrix_report_t;
int tel_report_write_matrix(tel_matrix_report_t *rep, const char *json_path, const char *seal_path);
void tel_report_free_matrix(tel_matrix_report_t *rep);
#endif
