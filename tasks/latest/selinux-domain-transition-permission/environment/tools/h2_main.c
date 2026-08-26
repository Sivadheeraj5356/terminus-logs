#include "epoch_ctx.h"
#include "carry_ctx.h"
#include "hop_cfg.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

extern int hop_peer(HostCfg *hc, const char *fixture_dir);
extern int probe_lane_gate(HostCfg *hc);
extern void snap_reset_pivot_cache(void);

static int journal_pivot(unsigned batch_no, const char *pivot)
{
    FILE *fp = fopen("/app/var/d8_pivot.jnl", "a");
    if (!fp) {
        return -1;
    }
    fprintf(fp, "{\"batch\":%u,\"pivot\":\"%s\"}\n", batch_no, pivot);
    fclose(fp);
    return 0;
}

static int run_fixture(const char *case_id, const char *fixture_dir, const char *pivot)
{
    HopSet set;
    FILE *out;
    unsigned ep;
    int i;

    (void)pivot;
    if (hops_load(fixture_dir, &set) != 0) {
        return -1;
    }
    ep = epoch_bump();
    carry_reset();
    snap_reset_pivot_cache();
    if (journal_pivot(ep, pivot) != 0) {
        return -1;
    }
    out = fopen("/app/var/d8_raw.jsonl", "a");
    if (!out) {
        return -1;
    }
    for (i = 0; i < set.count; i++) {
        HostCfg *hc = &set.items[i];
        snprintf(hc->case_id, sizeof hc->case_id, "%s", case_id);
        snprintf(hc->pivot, sizeof hc->pivot, "%s", pivot);
        hc->entry_idx = i;
        if (hop_peer(hc, fixture_dir) != 0) {
            fclose(out);
            return -1;
        }
        if (probe_lane_gate(hc) != 0) {
            fclose(out);
            return -1;
        }
        fprintf(out,
                "{\"case_id\":\"%s\",\"entry_idx\":%d,\"pivot\":\"%s\",\"epoch\":%u,"
                "\"gate_code\":\"%c\",\"cfg_mask\":%u,\"role_sample\":\"%s\","
                "\"role\":\"%s\",\"line\":\"%s\",\"list_mask\":%u,\"banner\":\"%s\"}\n",
                hc->case_id, hc->entry_idx, pivot, ep, hc->gate_code, hc->cfg_mask,
                hc->role_sample, hc->src.display, hc->line_text, hc->list_mask, hc->banner);
    }
    fclose(out);
    return 0;
}

static int parse_notes(void)
{
    FILE *fp = fopen("/app/docs/d8_run_notes.md", "r");
    char line[512];
    int rc = 0;

    if (!fp) {
        return -1;
    }
    epoch_reset();
    remove("/app/var/d8_raw.jsonl");
    remove("/app/var/d8_pivot.jnl");
    while (fgets(line, sizeof line, fp)) {
        char case_id[64];
        char fixture[256];
        char pivot[64];

        if (sscanf(line, " %63s %255s --pivot %63s", case_id, fixture, pivot) != 3) {
            continue;
        }
        if (run_fixture(case_id, fixture, pivot) != 0) {
            rc = -1;
        }
    }
    fclose(fp);
    return rc;
}

int main(void)
{
    if (parse_notes() != 0) {
        return 1;
    }
    return 0;
}
