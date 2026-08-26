#include "lane_forward.h"
#include "lane_resume.h"

#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>

int emit_backward(const char *zone, int64_t anchor, int cadence, const char *trace,
                  const char *out_dir, int *row_count);

typedef struct {
    char zone[64];
    int64_t anchor;
    int cadence;
    char pane[16];
} pane_cfg;

static int parse_env(const char *path, pane_cfg *cfg) {
    FILE *fp = fopen(path, "r");
    if (!fp) {
        return -1;
    }
    memset(cfg, 0, sizeof(*cfg));
    strcpy(cfg->zone, "US/Eastern");
    cfg->anchor = 1699142400;
    cfg->cadence = 1;
    char line[256];
    while (fgets(line, sizeof line, fp)) {
        char *eq = strchr(line, '=');
        if (!eq) {
            continue;
        }
        *eq = '\0';
        char *val = eq + 1;
        val[strcspn(val, "\r\n")] = '\0';
        if (strcmp(line, "zone") == 0) {
            strncpy(cfg->zone, val, sizeof(cfg->zone) - 1);
        } else if (strcmp(line, "anchor_epoch") == 0) {
            cfg->anchor = (int64_t)atoll(val);
        } else if (strcmp(line, "cadence_idx") == 0) {
            cfg->cadence = atoi(val);
        } else if (strcmp(line, "pane") == 0) {
            strncpy(cfg->pane, val, sizeof(cfg->pane) - 1);
        }
    }
    fclose(fp);
    return 0;
}

static int ensure_dir(const char *path) {
    if (mkdir(path, 0755) == 0 || errno == EEXIST) {
        return 0;
    }
    return -1;
}

static int write_frag_copy(const char *trace, const char *out_dir) {
    char frags[512];
    snprintf(frags, sizeof frags, "%s/frags", out_dir);
    if (ensure_dir(frags) != 0) {
        return -1;
    }
    FILE *in = fopen(trace, "r");
    if (!in) {
        return -2;
    }
    char line[256];
    int idx = 0;
    while (fgets(line, sizeof line, in)) {
        if (line[0] == '#' || line[0] == '\n') {
            continue;
        }
        char outpath[640];
        snprintf(outpath, sizeof outpath, "%s/frag_%03d.txt", frags, idx++);
        FILE *out = fopen(outpath, "w");
        if (!out) {
            fclose(in);
            return -3;
        }
        fputs(line, out);
        fclose(out);
    }
    fclose(in);
    return idx;
}

static void usage(const char *argv0) {
    fprintf(stderr, "usage: %s --pane ID --env PATH --trace PATH --out DIR\n", argv0);
}

int main(int argc, char **argv) {
    const char *pane = NULL;
    const char *env = NULL;
    const char *trace = NULL;
    const char *out = NULL;
    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--pane") == 0 && i + 1 < argc) {
            pane = argv[++i];
        } else if (strcmp(argv[i], "--env") == 0 && i + 1 < argc) {
            env = argv[++i];
        } else if (strcmp(argv[i], "--trace") == 0 && i + 1 < argc) {
            trace = argv[++i];
        } else if (strcmp(argv[i], "--out") == 0 && i + 1 < argc) {
            out = argv[++i];
        } else {
            usage(argv[0]);
            return 2;
        }
    }
    if (!pane || !env || !trace || !out) {
        usage(argv[0]);
        return 2;
    }
    pane_cfg cfg;
    if (parse_env(env, &cfg) != 0) {
        return 3;
    }
    strncpy(cfg.pane, pane, sizeof cfg.pane - 1);
    if (ensure_dir(out) != 0) {
        return 4;
    }
    if (write_frag_copy(trace, out) < 0) {
        return 5;
    }
    int row_count = 0;
    if (strcmp(cfg.pane, "backward") == 0) {
        if (emit_backward(cfg.zone, cfg.anchor, cfg.cadence, trace, out, &row_count) != 0) {
            return 6;
        }
    } else if (strcmp(cfg.pane, "forward") == 0) {
        if (emit_forward(cfg.zone, cfg.cadence, trace, out, &row_count) != 0) {
            return 6;
        }
    } else if (strcmp(cfg.pane, "resume") == 0) {
        if (emit_resume(cfg.zone, cfg.cadence, trace, out, &row_count) != 0) {
            return 6;
        }
    } else {
        return 7;
    }
    (void)row_count;
    return 0;
}
