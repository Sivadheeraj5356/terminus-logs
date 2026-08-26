#include "grant_buf.h"
#include "hop_cfg.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "sha256.h"

extern int pack_rows(const HostCfg *cfg, const AcceptSnap *live, FILE *out);

typedef struct {
    char case_id[DCASE_ID];
    int entry_idx;
    char pivot[64];
    unsigned epoch;
    char gate_code;
    uint32_t cfg_mask;
    char role_sample[HC_NAME];
    char role[HC_NAME];
    char line[HC_LINE];
    uint32_t list_mask;
    char banner[HC_NAME];
} RawRow;

static int read_raw(RawRow *rows, int cap, int *count)
{
    FILE *fp = fopen("/app/var/d8_raw.jsonl", "r");
    char line[1024];
    int n = 0;

    if (!fp) {
        return -1;
    }
    while (n < cap && fgets(line, sizeof line, fp)) {
        RawRow *r = &rows[n];
        char gc = 'D';
        unsigned ep = 0;
        unsigned list = 0;
        if (sscanf(line,
                   "{\"case_id\":\"%31[^\"]\",\"entry_idx\":%d,\"pivot\":\"%63[^\"]\","
                   "\"epoch\":%u,\"gate_code\":\"%c\",\"cfg_mask\":%u,"
                   "\"role_sample\":\"%127[^\"]\",\"role\":\"%127[^\"]\","
                   "\"line\":\"%255[^\"]\",\"list_mask\":%u,\"banner\":\"%127[^\"]\"}",
                   r->case_id, &r->entry_idx, r->pivot, &ep, &gc, &r->cfg_mask,
                   r->role_sample, r->role, r->line, &list, r->banner) != 11) {
            continue;
        }
        r->gate_code = gc;
        r->epoch = ep;
        r->list_mask = list;
        n++;
    }
    fclose(fp);
    *count = n;
    return n > 0 ? 0 : -1;
}

static void gate_digest(char digests[][9], int n, char out[65])
{
    char blob[4096];
    size_t pos = 0;
    int i;

    for (i = 0; i < n; i++) {
        size_t len = strlen(digests[i]);
        if (pos + len + 1 >= sizeof blob) {
            break;
        }
        if (i > 0) {
            blob[pos++] = '\n';
        }
        memcpy(blob + pos, digests[i], len);
        pos += len;
    }
    sha256_hex((const unsigned char *)blob, pos, out);
}

static int extract_row_digest(const char *json, char out[9])
{
    const char *key = strstr(json, "\"row_digest\":\"");
    if (!key) {
        return -1;
    }
    key += 14;
    memcpy(out, key, 8);
    out[8] = '\0';
    return 0;
}

extern int snap_read(const char *pivot_name, const char *role_text, AcceptSnap *out);
extern void snap_reset_pivot_cache(void);

int main(void)
{
    RawRow rows[24];
    char row_digests[24][9];
    char digest_full[65];
    FILE *out;
    int count = 0;
    int i;

    snap_reset_pivot_cache();
    if (read_raw(rows, 24, &count) != 0) {
        return 1;
    }
    out = fopen("/app/output/d8_observations.json", "w");
    if (!out) {
        return 1;
    }
    fprintf(out, "{\"profile\":\"security_authority_split\",\"rows\":[");
    for (i = 0; i < count; i++) {
        HostCfg cfg;
        AcceptSnap snap;
        FILE *mem;
        char buf[512];

        memset(&cfg, 0, sizeof cfg);
        snprintf(cfg.case_id, sizeof cfg.case_id, "%s", rows[i].case_id);
        cfg.entry_idx = rows[i].entry_idx;
        cfg.gate_code = rows[i].gate_code;
        cfg.cfg_mask = rows[i].cfg_mask;
        cfg.list_mask = rows[i].list_mask;
        snprintf(cfg.role_sample, sizeof cfg.role_sample, "%s", rows[i].role_sample);
        snprintf(cfg.src.display, sizeof cfg.src.display, "%s", rows[i].role);
        snprintf(cfg.line_text, sizeof cfg.line_text, "%s", rows[i].line);
        snap_read(rows[i].pivot, rows[i].role, &snap);

        mem = tmpfile();
        if (!mem) {
            return 1;
        }
        pack_rows(&cfg, &snap, mem);
        rewind(mem);
        if (!fgets(buf, sizeof buf, mem)) {
            fclose(mem);
            return 1;
        }
        fclose(mem);
        buf[strcspn(buf, "\n")] = '\0';
        if (extract_row_digest(buf, row_digests[i]) != 0) {
            return 1;
        }
        if (i > 0) {
            fprintf(out, ",");
        }
        fprintf(out, "%s", buf);
    }
    gate_digest(row_digests, count, digest_full);
    fprintf(out, "],\"gate_digest\":\"%s\"}\n", digest_full);
    fclose(out);

    {
        FILE *stamp = fopen("/app/var/d8_stamp.txt", "w");
        if (stamp) {
            fprintf(stamp, "%s\n", digest_full);
            fclose(stamp);
        }
    }
    return 0;
}
