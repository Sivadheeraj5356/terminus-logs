#include "../rowpack/row_fold.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define MAX_ROWS 128

static int load_pane_rows(const char *pane_dir, packed_row *rows, int *offset) {
    char path[512];
    snprintf(path, sizeof path, "%s/rows.tab", pane_dir);
    FILE *fp = fopen(path, "r");
    if (!fp) {
        return -1;
    }
    char pane[16];
    char key[32];
    int cyc, wall, seq, payload;
    while (fscanf(fp, "%d\t%15s\t%31s\t%d\t%d\t%d", &cyc, pane, key, &wall, &seq, &payload) ==
           6) {
        if (*offset >= MAX_ROWS) {
            break;
        }
        packed_row *r = &rows[*offset];
        memset(r, 0, sizeof(*r));
        r->cyc = cyc;
        strncpy(r->pane, pane, sizeof r->pane - 1);
        strncpy(r->day_key, key, sizeof r->day_key - 1);
        r->wall_off = wall;
        r->seq = seq;
        r->payload = payload;
        (*offset)++;
    }
    fclose(fp);
    return 0;
}

static int write_json(const char *out_path, const packed_row *rows, int count, const char *digest) {
    FILE *fp = fopen(out_path, "w");
    if (!fp) {
        return -1;
    }
    fprintf(fp, "{\n  \"rows\": [\n");
    for (int i = 0; i < count; i++) {
        fprintf(fp,
                "    {\"cycle\": %d, \"window\": \"%s\", \"civil_key\": \"%s\", "
                "\"wall_offset\": %d, \"seq\": %d, \"octets\": %d}%s\n",
                rows[i].cyc, rows[i].pane, rows[i].day_key, rows[i].wall_off, rows[i].seq,
                rows[i].payload, (i + 1 < count) ? "," : "");
    }
    fprintf(fp, "  ],\n  \"ledger_digest\": \"%s\"\n}\n", digest);
    fclose(fp);
    return 0;
}

int main(int argc, char **argv) {
    const char *step_root = NULL;
    const char *out = NULL;
    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--step-root") == 0 && i + 1 < argc) {
            step_root = argv[++i];
        } else if (strcmp(argv[i], "--out") == 0 && i + 1 < argc) {
            out = argv[++i];
        }
    }
    if (!step_root || !out) {
        fprintf(stderr, "usage: pack_tool --step-root DIR --out PATH\n");
        return 2;
    }
    packed_row rows[MAX_ROWS];
    int count = 0;
    const char *panes[] = {"backward", "forward", "resume"};
    for (int p = 0; p < 3; p++) {
        char dir[512];
        snprintf(dir, sizeof dir, "%s/%s", step_root, panes[p]);
        load_pane_rows(dir, rows, &count);
    }
    char digest[128];
    if (hash_rows(rows, count, digest, sizeof digest) != 0) {
        return 3;
    }
    if (write_json(out, rows, count, digest) != 0) {
        return 4;
    }
    return 0;
}
