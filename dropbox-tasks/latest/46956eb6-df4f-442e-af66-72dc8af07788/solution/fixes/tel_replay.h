#ifndef TEL_REPLAY_H
#define TEL_REPLAY_H
#include "tel_db.h"
#include "tel_report.h"
typedef struct {
    int samples_scanned;
    int errors_seen;
    int restarts_seen;
    int correlated_triples;
    uint64_t *affected_pids;
    size_t affected_pids_len;
    char leak_phase[32];
} tel_replay_stats_t;
int tel_replay_scenario(const tel_env_t *db, const char *scenario_id, int loops, tel_replay_stats_t *stats);
void tel_replay_stats_free(tel_replay_stats_t *stats);
#endif
