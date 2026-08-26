#include "lane_resume.h"
#include "commit_log.h"
#include "boot_era.h"

#include <stddef.h>
#include <stdio.h>
#include <string.h>

int emit_resume(const char *zone, int cadence, const char *trace, const char *out_dir,
                int *row_count) {
    (void)zone;
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
    char frags_dir[512];
    snprintf(frags_dir, sizeof frags_dir, "%s/frags", out_dir);
    char line[256];
    int count = 0;
    int idx = 0;
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
            idx++;
            continue;
        }
        (void)flags;
        int boot_gap = (wall_off >= 86400) ? 1 : 0;
        char frag_path[640];
        snprintf(frag_path, sizeof frag_path, "%s/frag_%03d.txt", frags_dir, idx++);
        int exec_it = 0;
        decide_sweep(frag_path, boot_gap, 0, &exec_it);
        if (boot_gap && !exec_it) {
            continue;
        }
        char canon[32];
        if (reconcile_key(recon_path, canon, sizeof canon) != 0) {
            strncpy(canon, key, sizeof canon - 1);
        }
        fprintf(rows_fp, "%d\tresume\t%s\t%d\t%d\t%d\n", cadence, canon, wall_off, seq,
                64 + (seq * 8));
        commit_log_append(COMMIT_LOG_PATH, "resume", canon, seq, flags);
        count++;
    }
    fclose(in);
    FILE *rin = fopen(trace, "r");
    if (rin) {
        char rline[256];
        int ridx = 0;
        while (fgets(rline, sizeof rline, rin)) {
            if (rline[0] == '#' || rline[0] == '\n') {
                continue;
            }
            rline[strcspn(rline, "\r\n")] = '\0';
            char key[32];
            int wall_off = 0;
            int seq = 0;
            int flags = 0;
            if (sscanf(rline, "%31[^|]|%d|%d|%i", key, &wall_off, &seq, &flags) < 3) {
                ridx++;
                continue;
            }
            (void)flags;
            char frag_path[640];
            snprintf(frag_path, sizeof frag_path, "%s/frag_%03d.txt", frags_dir, ridx);
            int exec_it = 0;
            decide_sweep(frag_path, 1, 1, &exec_it);
            if (exec_it) {
                char canon[32];
                if (reconcile_key(recon_path, canon, sizeof canon) != 0) {
                    strncpy(canon, key, sizeof canon - 1);
                }
                fprintf(rows_fp, "%d\tresume\t%s\t%d\t%d\t%d\n", cadence, canon, wall_off,
                        seq + 100, 96);
                commit_log_append(COMMIT_LOG_PATH, "resume", canon, seq + 100, flags);
                count++;
            }
            ridx++;
        }
        fclose(rin);
    }
    boot_era_bump(BOOT_ERA_PATH);
    fclose(recon_src);
    fclose(rows_fp);
    *row_count = count;
    return 0;
}
