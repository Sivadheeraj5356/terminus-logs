#include "tel_replay.h"

#include "tel_correlate.h"
#include "tel_config.h"
#include "tel_fd.h"
#include "tel_scan.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int tel_replay_scenario(const tel_env_t *db, const char *scenario_id, int loops,
                        tel_replay_stats_t *stats) {
    memset(stats, 0, sizeof(*stats));
    strcpy(stats->leak_phase, "none");

    int sample_total = 0;
    int error_total = 0;
    for (int i = 0; i < loops; i++) {
        int sc = 0;
        if (tel_scan_samples_once(db, &sc) != 0) {
            return -1;
        }
        sample_total = sc;
        int ec = 0;
        if (tel_correlate_errors_once(db, &ec) != 0) {
            return -1;
        }
        error_total = ec;
    }

    stats->samples_scanned = sample_total;
    stats->errors_seen = error_total;

    tel_restart_row_t *restarts = NULL;
    size_t restart_len = 0;
    if (tel_compute_correlation(db, scenario_id, restarts, restart_len, stats) != 0) {
        return -1;
    }

    if (tel_walk_restarts_once(db, &restarts, &restart_len) != 0) {
        return -1;
    }
    stats->restarts_seen = (int)restart_len;
    free(restarts);

    int fd_before = tel_count_open_fds();
    for (int i = 0; i < loops; i++) {
        int sc = 0;
        tel_scan_samples_once(db, &sc);
        int ec = 0;
        tel_correlate_errors_once(db, &ec);
        tel_restart_row_t *rows = NULL;
        size_t rl = 0;
        tel_walk_restarts_once(db, &rows, &rl);
        free(rows);
    }
    int fd_after = tel_count_open_fds();
    int delta = fd_after - fd_before;
    if (delta > 0) {
        if (delta >= loops * 2) {
            strcpy(stats->leak_phase, "restart_walk");
        } else if (delta >= loops) {
            strcpy(stats->leak_phase, "sample_scan");
        } else {
            strcpy(stats->leak_phase, "error_correlate");
        }
    }
    return 0;
}

void tel_replay_stats_free(tel_replay_stats_t *stats) {
    free(stats->affected_pids);
    stats->affected_pids = NULL;
    stats->affected_pids_len = 0;
}
