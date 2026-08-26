#!/bin/bash
set -euo pipefail

cd /app/environment

cat > mask/k5_row.c <<'EOF'
#include "grant_buf.h"
#include "role_snap.h"

#include <stdio.h>

int pick_mask(const RoleSnap *a, const RoleSnap *b, GrantBuf *out)
{
    if (!a || !b || !out) {
        return -1;
    }
    (void)a;
    out->mask = b->cap_bits;
    return 0;
}
EOF

cat > bound/h2_cap.c <<'EOF'
#include "grant_buf.h"
#include "role_snap.h"

#include <stdio.h>

int bind_cap(const RoleSnap *b, CapSet *out)
{
    if (!b || !out) {
        return -1;
    }
    out->bits = b->cap_bits;
    return 0;
}
EOF

cat > lane/m3_fd.c <<'EOF'
#include "grant_buf.h"

#include <stdio.h>

int scan_lane(int fd, const GrantBuf *a, const GrantBuf *b, int *ok)
{
    uint32_t bits;

    if (!a || !b || !ok || fd < 0) {
        return -1;
    }
    bits = b->mask;
    *ok = (bits & (1u << (unsigned)fd)) != 0 ? 1 : 0;
    (void)a;
    return 0;
}
EOF

cat > s6_host/s6_emit.c <<'EOF'
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
             row->gate_code, row->cfg_mask, row->sample_mask, row->live_mask,
             row->role_sample);
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
    if (cfg->gate_code == 'A' && live && live->count > 0) {
        row.sample_mask = live->mask[0];
        row.live_mask = live->mask[0];
    } else {
        row.sample_mask = 0;
        row.live_mask = 0;
    }
    snprintf(row.role_sample, sizeof row.role_sample, "%s", cfg->role_sample);
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
EOF

cat > state/k4_carry.c <<'EOF'
#include "carry_ctx.h"

static unsigned g_carry;
static unsigned g_lane_hist;

void carry_reset(void)
{
    g_carry = 0;
    g_lane_hist = 0;
}

void carry_fold(unsigned lane_fd)
{
    if (lane_fd < 32u) {
        g_carry |= (1u << lane_fd);
        g_lane_hist |= (1u << lane_fd);
    }
}

unsigned carry_peek(void)
{
    return g_carry | g_lane_hist;
}
EOF

cat > snap/n3_snap.c <<'EOF'
#include "grant_buf.h"
#include "role_snap.h"

#include <stdio.h>
#include <string.h>

extern int r9_apply_kind(const RoleSnap *snap, char *buf, size_t cap, BufKind *kind_out);
extern uint32_t tag_from_pair(const char *a, const char *b, int slot);

static int split_pivot(const char *line, TokList *out)
{
    char buf[256];
    char *tok;
    char *save = NULL;

    if (!line || !out) {
        return -1;
    }
    memset(out, 0, sizeof *out);
    snprintf(buf, sizeof buf, "%s", line);
    for (tok = strtok_r(buf, ",", &save); tok && out->count < NL_MAX;
         tok = strtok_r(NULL, ",", &save)) {
        snprintf(out->items[out->count], sizeof out->items[out->count], "%s", tok);
        out->count++;
    }
    return out->count > 0 ? 0 : -1;
}

static int load_pivot_line(const char *pivot_name, char *line, size_t cap)
{
    char path[256];
    FILE *fp;

    snprintf(path, sizeof path, "/app/work/pivot/%s.txt", pivot_name);
    fp = fopen(path, "r");
    if (!fp) {
        return -1;
    }
    if (fgets(line, (int)cap, fp) == NULL) {
        fclose(fp);
        return -1;
    }
    line[strcspn(line, "\n")] = '\0';
    fclose(fp);
    return 0;
}

int snap_from_name(const char *want, const char *line, AcceptSnap *out)
{
    TokList tokens;
    int i;

    if (!want || !line || !out) {
        return -1;
    }
    memset(out, 0, sizeof *out);
    if (split_pivot(line, &tokens) != 0) {
        return -1;
    }
    for (i = 0; i < tokens.count && out->count < 4; i++) {
        char left[RB_MAX];
        char right[RB_MAX];
        size_t left_len;
        size_t right_len;
        BufKind kind = BK_U8;

        snprintf(left, sizeof left, "%s", want);
        snprintf(right, sizeof right, "%s", tokens.items[i]);
        r9_apply_kind(&(RoleSnap){.kind = BK_U8}, left, sizeof left, &kind);
        r9_apply_kind(&(RoleSnap){.kind = BK_U8}, right, sizeof right, &kind);
        left_len = strlen(left);
        right_len = strlen(right);
        if (left_len == right_len && memcmp(left, right, left_len) == 0) {
            out->mask[out->count++] = tag_from_pair(want, tokens.items[i], i);
        }
    }
    return 0;
}

static char cached_role[RB_MAX];
static char cached_pivot[64];
static AcceptSnap cached_snap;
static int have_cached;

int snap_read(const char *pivot_name, const char *role_text, AcceptSnap *out)
{
    char line[256];

    if (!pivot_name || !role_text || !out) {
        return -1;
    }
    if (have_cached && strcmp(role_text, cached_role) == 0 &&
        strcmp(pivot_name, cached_pivot) == 0) {
        *out = cached_snap;
        return 0;
    }
    if (load_pivot_line(pivot_name, line, sizeof line) != 0) {
        return -1;
    }
    if (snap_from_name(role_text, line, out) != 0) {
        return -1;
    }
    snprintf(cached_role, sizeof cached_role, "%s", role_text);
    snprintf(cached_pivot, sizeof cached_pivot, "%s", pivot_name);
    cached_snap = *out;
    have_cached = 1;
    return 0;
}

void snap_reset_pivot_cache(void)
{
    have_cached = 0;
}
EOF

make -C /app/environment all -j2
/app/tools/h2_runner
/app/tools/q1_emit
