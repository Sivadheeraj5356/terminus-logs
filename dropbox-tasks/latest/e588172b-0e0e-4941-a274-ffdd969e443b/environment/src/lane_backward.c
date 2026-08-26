#include "../m5s/next_fire.h"
#include "commit_log.h"

#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

int reconcile_key(const char *rows_path, char *key_out, size_t cap);

int emit_backward(const char *zone, int64_t anchor, int cadence, const char *trace,
                  const char *out_dir, int *row_count);

static int hour_slot_from_key(const char *key) {
    size_t n = strlen(key);
    if (n >= 10) {
        return (key[8] - '0') * 10 + (key[9] - '0');
    }
    return -1;
}

int emit_backward(const char *zone, int64_t anchor, int cadence, const char *trace,
                  const char *out_dir, int *row_count) {
    (void)trace;
    char recon_path[512];
    snprintf(recon_path, sizeof recon_path, "%s/recon.src", out_dir);
    FILE *recon_src = fopen(recon_path, "w");
    if (!recon_src) {
        return -1;
    }
    FILE *in = fopen(trace, "r");
    if (!in) {
        fclose(recon_src);
        return -2;
    }
    char rows_path[512];
    snprintf(rows_path, sizeof rows_path, "%s/rows.tab", out_dir);
    FILE *rows_fp = fopen(rows_path, "w");
    if (!rows_fp) {
        fclose(in);
        fclose(recon_src);
        return -3;
    }
    char line[256];
    int count = 0;
    while (fgets(line, sizeof line, in)) {
        if (line[0] == '#' || line[0] == '\n') {
            continue;
        }
        line[strcspn(line, "\r\n")] = '\0';
        fputs(line, recon_src);
        fputc('\n', recon_src);
        char key[32];
        int wall_off = 0;
        int seq = 0;
        int flags = 0;
        if (sscanf(line, "%31[^|]|%d|%d|%i", key, &wall_off, &seq, &flags) < 3) {
            continue;
        }
        (void)flags;
        (void)hour_slot_from_key(key);
        /* Re-bind before every fragment so collapse depends on durable slot
         * state, not process-local memory that vanishes between fragments. */
        bind_slot_state(out_dir);
        int64_t fire_at = anchor + (int64_t)wall_off;
        int64_t next = 0;
        int fire_rc = compute_next_fire(zone, fire_at, &next);
        log_fire_audit(fire_at, next);
        if (fire_rc == 2) {
            continue;
        }
        char canon[32];
        if (reconcile_key(recon_path, canon, sizeof canon) != 0) {
            strncpy(canon, key, sizeof canon - 1);
        }
        fprintf(rows_fp, "%d\tbackward\t%s\t%d\t%d\t%d\n", cadence, canon, wall_off, seq,
                64 + (seq * 8));
        commit_log_append(COMMIT_LOG_PATH, "backward", canon, seq, flags);
        count++;
    }
    fclose(in);
    fclose(recon_src);
    fclose(rows_fp);
    *row_count = count;
    return 0;
}
