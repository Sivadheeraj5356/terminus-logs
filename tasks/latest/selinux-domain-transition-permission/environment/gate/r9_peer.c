#include "grant_buf.h"
#include "hop_cfg.h"
#include "role_snap.h"

#include <stdio.h>
#include <string.h>

extern int pick_mask(const RoleSnap *a, const RoleSnap *b, GrantBuf *out);
extern int bind_cap(const RoleSnap *b, CapSet *out);
extern int r9_alt(const RoleSnap *a, const RoleSnap *b, char *out, size_t cap, size_t *out_len,
                  BufKind *kind_out, const RoleSnap **pick_out);
extern int r9_apply_kind(const RoleSnap *snap, char *buf, size_t cap, BufKind *kind_out);
extern uint32_t tag_from_pair(const char *a, const char *b, int slot);
extern int snap_from_name(const char *want, const char *line, AcceptSnap *out);

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

static int match_row(const char *role, const char *row, int *slot)
{
    char left[RB_MAX];
    char right[RB_MAX];
    size_t left_len;
    size_t right_len;
    BufKind kind = BK_U8;

    if (!role || !row || !slot) {
        return -1;
    }
    snprintf(left, sizeof left, "%s", role);
    snprintf(right, sizeof right, "%s", row);
    r9_apply_kind(&(RoleSnap){.kind = BK_U8}, left, sizeof left, &kind);
    left_len = strlen(left);
    right_len = strlen(right);
    if (left_len != right_len) {
        *slot = -1;
        return 0;
    }
    if (memcmp(left, right, left_len) == 0) {
        *slot = 0;
        return 0;
    }
    *slot = -1;
    return 0;
}

static int active_role(HostCfg *hc, char *buf, size_t cap, size_t *role_len, BufKind *kind)
{
    const RoleSnap *pick = &hc->src;

    if (r9_alt(&hc->src, &hc->alt, buf, cap, role_len, kind, &pick) != 0) {
        return -1;
    }
    if (r9_apply_kind(pick, buf, cap, kind) != 0) {
        return -1;
    }
    *role_len = strlen(buf);
    return 1;
}

int hop_peer(HostCfg *hc, const char *fixture_dir)
{
    GrantBuf hop_mask;
    CapSet caps;
    int slot = -1;
    char buf[RB_MAX];
    char list_line[HC_LINE];
    FILE *fp;
    char path[512];
    size_t role_len = 0;
    BufKind kind = BK_A5;

    (void)fixture_dir;
    if (!hc) {
        return -1;
    }
    if (active_role(hc, buf, sizeof buf, &role_len, &kind) <= 0) {
        return -1;
    }
    if (strcmp(buf, hc->pair_label) != 0) {
        snprintf(hc->banner, sizeof hc->banner, "peer fail");
        hc->gate_code = 'D';
        hc->cfg_mask = 0;
        snprintf(hc->role_sample, sizeof hc->role_sample, "%s", hc->src.display);
        return 0;
    }
    {
        RoleSnap tgt_mask = hc->alt;
        tgt_mask.cap_bits = hc->row_bits;
        if (pick_mask(&hc->src, &tgt_mask, &hop_mask) != 0) {
            return -1;
        }
    }
    {
        RoleSnap ceil_snap = hc->alt;
        ceil_snap.cap_bits = hc->cap_ceil;
        if (bind_cap(&ceil_snap, &caps) != 0) {
            return -1;
        }
    }
    hc->mask_bits = hop_mask.mask;
    hc->bound_bits = caps.bits;
    if (match_row(buf, hc->line_text, &slot) != 0) {
        return -1;
    }
    hc->gate_code = slot >= 0 ? 'A' : 'D';
    if (slot >= 0) {
        char pivot_line[256];
        AcceptSnap snap;
        snprintf(hc->role_sample, sizeof hc->role_sample, "%s", hc->line_text);
        hc->cfg_mask = 0;
        if (hc->pivot[0] && load_pivot_line(hc->pivot, pivot_line, sizeof pivot_line) == 0 &&
            snap_from_name(buf, pivot_line, &snap) == 0 && snap.count > 0) {
            hc->cfg_mask = snap.mask[0];
        }
    } else {
        snprintf(hc->role_sample, sizeof hc->role_sample, "%s", hc->src.display);
        hc->cfg_mask = 0;
    }
    snprintf(hc->src.display, sizeof hc->src.display, "%s", buf);

    snprintf(path, sizeof path, "%s/tgt.te", fixture_dir);
    fp = fopen(path, "r");
    list_line[0] = '\0';
    if (fp) {
        char ln[HC_LINE];
        while (fgets(ln, sizeof ln, fp)) {
            if (strncmp(ln, "LIST:", 5) == 0) {
                ln[strcspn(ln, "\n")] = '\0';
                snprintf(list_line, sizeof list_line, "%s", ln + 5);
                break;
            }
        }
        fclose(fp);
    }
    if (!list_line[0]) {
        snprintf(list_line, sizeof list_line, "%s", hc->pair_label);
    }
    hc->list_mask = tag_from_pair(hc->src.display, list_line, 0);
    snprintf(hc->banner, sizeof hc->banner, "peer ok");
    (void)hop_mask;
    (void)caps;
    return 0;
}
