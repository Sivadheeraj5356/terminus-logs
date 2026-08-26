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

int snap_read(const char *pivot_name, const char *role_text, AcceptSnap *out)
{
    char line[256];
    static char cached_role[RB_MAX];
    static AcceptSnap cached_snap;
    static int have_cached;

    if (!pivot_name || !role_text || !out) {
        return -1;
    }
    if (have_cached && strcmp(role_text, cached_role) == 0) {
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
    cached_snap = *out;
    have_cached = 1;
    return 0;
}

void snap_reset_pivot_cache(void)
{
}
