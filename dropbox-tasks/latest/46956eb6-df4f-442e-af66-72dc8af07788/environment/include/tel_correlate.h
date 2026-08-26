#ifndef TEL_CORRELATE_H
#define TEL_CORRELATE_H

#include "tel_db.h"
#include "tel_replay.h"
#include "tel_scan.h"

int tel_correlate_errors_once(const tel_env_t *db, int *count_out);
int tel_compute_correlation(const tel_env_t *db, const char *scenario_id,
                            tel_restart_row_t *restarts, size_t restart_len,
                            tel_replay_stats_t *stats);

#endif
