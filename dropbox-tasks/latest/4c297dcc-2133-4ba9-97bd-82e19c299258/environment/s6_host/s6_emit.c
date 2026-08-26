#include "grant_buf.h"
#include "hop_cfg.h"

#include <stdio.h>
#include <string.h>

#include "sha256.h"

typedef struct {
    char case_id[DCASE_ID];
    int entry_idx;
    char role_text[HC_NAME];
    char line_text[HC_LINE];
    char gate_code;
    uint32_t cfg_mask;
    uint32_t sample_mask;
    uint32_t live_mask;
    char role_sample[HC_NAME];
    char row_digest[9];
} ObsRow;

static void line_fp(ObsRow *row)
{
    char body[512];
    char hex[65];

    snprintf(body, sizeof body, "%s|%d|%c|%u|%u|%u|%s", row->case_id, row->entry_idx,
             row->gate_code, row->cfg_mask, row->sample_mask, row->live_mask, row->role_sample);
    sha256_hex((const unsigned char *)body, strlen(body), hex);
    memcpy(row->row_digest, hex, 8);
    row->row_digest[8] = '\0';
}

int pack_rows(const HostCfg *cfg, const AcceptSnap *live, FILE *out)
{
    ObsRow row;

    if (!cfg || !out) {
        return -1;
    }
    memset(&row, 0, sizeof row);
    snprintf(row.case_id, sizeof row.case_id, "%s", cfg->case_id);
    row.entry_idx = cfg->entry_idx;
    snprintf(row.role_text, sizeof row.role_text, "%s", cfg->src.display);
    snprintf(row.line_text, sizeof row.line_text, "%s", cfg->line_text);
    row.gate_code = cfg->gate_code;
    row.cfg_mask = cfg->cfg_mask;
    row.sample_mask = cfg->list_mask;
    row.live_mask = cfg->list_mask;
    snprintf(row.role_sample, sizeof row.role_sample, "%s", cfg->role_sample);
    (void)live;
    line_fp(&row);

    fprintf(out,
            "{\"case_id\":\"%s\",\"entry_idx\":%d,"
            "\"role_text\":\"%s\",\"line_text\":\"%s\","
            "\"gate_code\":\"%c\",\"cfg_mask\":%u,\"sample_mask\":%u,"
            "\"live_mask\":%u,\"role_sample\":\"%s\",\"row_digest\":\"%s\"}\n",
            row.case_id, row.entry_idx, row.role_text, row.line_text, row.gate_code,
            row.cfg_mask, row.sample_mask, row.live_mask, row.role_sample, row.row_digest);
    return 0;
}
