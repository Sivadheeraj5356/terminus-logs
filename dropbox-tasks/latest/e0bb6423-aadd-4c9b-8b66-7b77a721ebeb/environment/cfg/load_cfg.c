#include "pamlink/cfg.h"
#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define STACKS_PATH "/app/config/stack_table.json"
#define ACCTS_PATH "/app/config/accounts.json"
#define DENY_PATH "/app/config/a7_threshold.toml"
#define MODULES_PATH "/app/config/m3_weights.toml"
#define REALM_PATH "/app/config/n9_view.toml"
#define OVERRIDE_PATH "/app/config/k2_bindings.toml"
#define LEDGER_DIR "/app/var/tally"
#define PLANE_A "/app/ctl/p_a.json"
#define PLANE_B "/app/ctl/p_b.json"
#define PLANE_C "/app/ctl/p_c.json"
#define RT_OPTS "/app/rt/opts.json"

static int read_file(const char *path, char *buf, size_t buflen) {
    FILE *f = fopen(path, "r");
    if (!f) {
        return -1;
    }
    size_t n = fread(buf, 1, buflen - 1, f);
    fclose(f);
    buf[n] = '\0';
    return (int)n;
}

static int json_int_field(const char *blob, const char *key, int *out) {
    char needle[64];
    snprintf(needle, sizeof(needle), "\"%s\"", key);
    const char *p = strstr(blob, needle);
    if (!p) {
        return -1;
    }
    p = strchr(p + strlen(needle), ':');
    if (!p) {
        return -1;
    }
    p++;
    while (*p && isspace((unsigned char)*p)) {
        p++;
    }
    *out = atoi(p);
    return 0;
}

static int json_bool_field(const char *blob, const char *key, int *out) {
    char needle[64];
    snprintf(needle, sizeof(needle), "\"%s\"", key);
    const char *p = strstr(blob, needle);
    if (!p) {
        return -1;
    }
    p = strchr(p + strlen(needle), ':');
    if (!p) {
        return -1;
    }
    p++;
    while (*p && isspace((unsigned char)*p)) {
        p++;
    }
    if (strncmp(p, "true", 4) == 0) {
        *out = 1;
        return 0;
    }
    if (strncmp(p, "false", 5) == 0) {
        *out = 0;
        return 0;
    }
    return -1;
}

static int json_string_field(const char *blob, const char *key, char *out, size_t out_len) {
    char needle[64];
    snprintf(needle, sizeof(needle), "\"%s\"", key);
    const char *p = strstr(blob, needle);
    if (!p) {
        return -1;
    }
    p = strchr(p + strlen(needle), ':');
    if (!p) {
        return -1;
    }
    p = strchr(p, '"');
    if (!p) {
        return -1;
    }
    p++;
    const char *end = strchr(p, '"');
    if (!end) {
        return -1;
    }
    size_t len = (size_t)(end - p);
    if (len >= out_len) {
        len = out_len - 1;
    }
    memcpy(out, p, len);
    out[len] = '\0';
    return 0;
}

static int rt_honor_legacy_overrides(void) {
    char buf[4096];
    if (read_file(RT_OPTS, buf, sizeof(buf)) < 0) {
        return 1;
    }
    int honor = 1;
    if (json_bool_field(buf, "honor_legacy_overrides", &honor) != 0) {
        return 1;
    }
    return honor;
}

static int parse_stack_chunk(const char *blob, stack_row *row) {
    const char *p;
    if ((p = strstr(blob, "\"id\"")) == NULL) {
        return -1;
    }
    sscanf(p, "\"id\": \"%31[^\"]\"", row->id);
    if ((p = strstr(blob, "\"service\"")) == NULL) {
        return -1;
    }
    sscanf(p, "\"service\": \"%127[^\"]\"", row->service);
    row->mod_count = 0;
    const char *mods = strstr(blob, "\"modules\"");
    if (mods) {
        mods = strchr(mods, '[');
        if (mods) {
            mods++;
            while (*mods && *mods != ']' && row->mod_count < PL_MAX_MOD) {
                const char *q = strchr(mods, '\"');
                if (!q) {
                    break;
                }
                q++;
                const char *end = strchr(q, '\"');
                if (!end) {
                    break;
                }
                size_t len = (size_t)(end - q);
                if (len >= PL_NAME_MAX) {
                    len = PL_NAME_MAX - 1;
                }
                char tmp[PL_NAME_MAX];
                memcpy(tmp, q, len);
                tmp[len] = '\0';
                strncpy(row->modules[row->mod_count++], tmp, PL_NAME_MAX - 1);
                mods = end + 1;
            }
        }
    }
    return 0;
}

int cfg_load_stacks(stack_table *tbl, const char *path) {
    char buf[16384];
    if (read_file(path ? path : STACKS_PATH, buf, sizeof(buf)) < 0) {
        return -1;
    }
    tbl->count = 0;
    const char *cursor = buf;
    while ((cursor = strstr(cursor, "{")) != NULL && tbl->count < PL_MAX_STACK) {
        const char *end = strchr(cursor, '}');
        if (!end) {
            break;
        }
        char chunk[1024];
        size_t len = (size_t)(end - cursor + 1);
        if (len >= sizeof(chunk)) {
            break;
        }
        memcpy(chunk, cursor, len);
        chunk[len] = '\0';
        if (parse_stack_chunk(chunk, &tbl->rows[tbl->count]) == 0) {
            tbl->count++;
        }
        cursor = end + 1;
    }
    return tbl->count > 0 ? 0 : -1;
}

static int load_roster_from_plane(acct_table *tbl) {
    char buf[16384];
    if (read_file(PLANE_C, buf, sizeof(buf)) < 0) {
        return -1;
    }
    int prefer = 0;
    if (json_bool_field(buf, "prefer_roster", &prefer) != 0 || !prefer) {
        return -1;
    }
    const char *roster = strstr(buf, "\"roster\"");
    if (!roster) {
        return -1;
    }
    roster = strchr(roster, '{');
    if (!roster) {
        return -1;
    }
    tbl->count = 0;
    const char *cursor = roster + 1;
    while (tbl->count < PL_MAX_ACCT) {
        const char *q = strchr(cursor, '"');
        if (!q) {
            break;
        }
        char actor[PL_NAME_MAX];
        if (sscanf(q, "\"%127[^\"]\"", actor) != 1) {
            break;
        }
        if (strchr(actor, '@') == NULL) {
            cursor = q + 1;
            continue;
        }
        const char *colon = strchr(q + strlen(actor) + 2, ':');
        if (!colon) {
            break;
        }
        int64_t val = (int64_t)atoll(colon + 1);
        strncpy(tbl->rows[tbl->count].actor, actor, PL_NAME_MAX - 1);
        tbl->rows[tbl->count].actor[PL_NAME_MAX - 1] = '\0';
        tbl->rows[tbl->count].expiry = val;
        tbl->count++;
        cursor = colon + 1;
        if (*cursor == '}') {
            break;
        }
    }
    return tbl->count > 0 ? 0 : -1;
}

int cfg_load_accts(acct_table *tbl, const char *path) {
    if (load_roster_from_plane(tbl) == 0) {
        return 0;
    }
    char buf[16384];
    if (read_file(path ? path : ACCTS_PATH, buf, sizeof(buf)) < 0) {
        return -1;
    }
    tbl->count = 0;
    const char *cursor = buf;
    while ((cursor = strstr(cursor, "\"")) != NULL && tbl->count < PL_MAX_ACCT) {
        char actor[PL_NAME_MAX];
        if (sscanf(cursor, "\"%127[^\"]\"", actor) != 1) {
            break;
        }
        if (strchr(actor, '@') == NULL) {
            cursor++;
            continue;
        }
        const char *exp = strstr(cursor, "\"expiry\"");
        if (!exp) {
            break;
        }
        int64_t val = 0;
        sscanf(exp, "\"expiry\": %lld", (long long *)&val);
        strncpy(tbl->rows[tbl->count].actor, actor, PL_NAME_MAX - 1);
        tbl->rows[tbl->count].expiry = val;
        tbl->count++;
        cursor = exp + 1;
    }
    return tbl->count > 0 ? 0 : -1;
}

int cfg_load_deny(const char *path) {
    char buf[8192];
    if (read_file(PLANE_A, buf, sizeof(buf)) >= 0) {
        int deny = 0;
        if (json_int_field(buf, "deny", &deny) == 0 && deny > 0) {
            return deny;
        }
    }
    FILE *f = fopen(path ? path : DENY_PATH, "r");
    if (!f) {
        return 3;
    }
    char line[256];
    int deny = 3;
    while (fgets(line, sizeof(line), f)) {
        if (strncmp(line, "deny =", 6) == 0) {
            deny = atoi(line + 6);
        }
    }
    fclose(f);
    return deny;
}

static void trim(char *s) {
    size_t n = strlen(s);
    while (n > 0 && isspace((unsigned char)s[n - 1])) {
        s[--n] = '\0';
    }
    char *p = s;
    while (*p && isspace((unsigned char)*p)) {
        p++;
    }
    if (p != s) {
        memmove(s, p, strlen(p) + 1);
    }
}

int cfg_load_count_modules(char mods[][PL_NAME_MAX], int max, int *out_n) {
    char buf[8192];
    if (read_file(PLANE_A, buf, sizeof(buf)) >= 0) {
        const char *arr = strstr(buf, "\"count_modules\"");
        if (arr) {
            arr = strchr(arr, '[');
            if (arr) {
                arr++;
                int count = 0;
                while (*arr && *arr != ']' && count < max) {
                    const char *q = strchr(arr, '"');
                    if (!q) {
                        break;
                    }
                    q++;
                    const char *end = strchr(q, '"');
                    if (!end) {
                        break;
                    }
                    size_t len = (size_t)(end - q);
                    if (len >= PL_NAME_MAX) {
                        len = PL_NAME_MAX - 1;
                    }
                    memcpy(mods[count], q, len);
                    mods[count][len] = '\0';
                    count++;
                    arr = end + 1;
                }
                if (count > 0) {
                    *out_n = count;
                    return 0;
                }
            }
        }
    }

    FILE *f = fopen(MODULES_PATH, "r");
    if (!f) {
        return -1;
    }
    char line[256];
    int in_list = 0;
    int count = 0;
    while (fgets(line, sizeof(line), f)) {
        trim(line);
        if (strstr(line, "count_modules")) {
            in_list = strchr(line, '[') != NULL;
        }
        if (!in_list) {
            continue;
        }
        const char *q = strchr(line, '"');
        while (q && count < max) {
            q++;
            const char *end = strchr(q, '"');
            if (!end) {
                break;
            }
            size_t len = (size_t)(end - q);
            if (len >= PL_NAME_MAX) {
                len = PL_NAME_MAX - 1;
            }
            memcpy(mods[count], q, len);
            mods[count][len] = '\0';
            count++;
            q = strchr(end + 1, '"');
        }
        if (strchr(line, ']')) {
            break;
        }
    }
    fclose(f);
    *out_n = count;
    return count > 0 ? 0 : -1;
}

int cfg_load_realm_mode(char *mode, size_t mode_len) {
    char buf[8192];
    if (read_file(PLANE_C, buf, sizeof(buf)) >= 0) {
        if (json_string_field(buf, "realm_mode", mode, mode_len) == 0) {
            return 0;
        }
    }
    FILE *f = fopen(REALM_PATH, "r");
    if (!f) {
        strncpy(mode, "lower", mode_len - 1);
        mode[mode_len - 1] = '\0';
        return -1;
    }
    char line[256];
    while (fgets(line, sizeof(line), f)) {
        if (strncmp(line, "realm_mode", 10) == 0) {
            const char *eq = strchr(line, '=');
            if (!eq) {
                continue;
            }
            eq++;
            while (*eq && isspace((unsigned char)*eq)) {
                eq++;
            }
            char tmp[32];
            if (sscanf(eq, "%31s", tmp) == 1) {
                strncpy(mode, tmp, mode_len - 1);
                mode[mode_len - 1] = '\0';
                fclose(f);
                return 0;
            }
        }
    }
    fclose(f);
    strncpy(mode, "lower", mode_len - 1);
    mode[mode_len - 1] = '\0';
    return 0;
}

static int plane_b_force_map(const char *svc, char *out, size_t out_len) {
    char buf[8192];
    if (read_file(PLANE_B, buf, sizeof(buf)) < 0) {
        return -1;
    }
    const char *map = strstr(buf, "\"force_map\"");
    if (!map) {
        return -1;
    }
    map = strchr(map, '{');
    if (!map) {
        return -1;
    }
    char needle[160];
    snprintf(needle, sizeof(needle), "\"%s\"", svc);
    const char *hit = strstr(map, needle);
    if (!hit) {
        return -1;
    }
    const char *colon = strchr(hit, ':');
    if (!colon) {
        return -1;
    }
    const char *q = strchr(colon, '"');
    if (!q) {
        return -1;
    }
    q++;
    const char *end = strchr(q, '"');
    if (!end) {
        return -1;
    }
    size_t len = (size_t)(end - q);
    if (len >= out_len) {
        len = out_len - 1;
    }
    memcpy(out, q, len);
    out[len] = '\0';
    return 0;
}

static int plane_b_reject_override(void) {
    char buf[8192];
    if (read_file(PLANE_B, buf, sizeof(buf)) < 0) {
        return 0;
    }
    int reject = 0;
    if (json_bool_field(buf, "reject_override", &reject) != 0) {
        return 0;
    }
    return reject;
}

int cfg_lookup_stack_override(const char *svc, char *out, size_t out_len) {
    if (plane_b_force_map(svc, out, out_len) == 0) {
        return 0;
    }
    if (plane_b_reject_override() || !rt_honor_legacy_overrides()) {
        return -1;
    }
    FILE *f = fopen(OVERRIDE_PATH, "r");
    if (!f) {
        return -1;
    }
    char line[256];
    char cur_svc[PL_NAME_MAX] = {0};
    while (fgets(line, sizeof(line), f)) {
        trim(line);
        if (line[0] == '\0' || line[0] == '#') {
            continue;
        }
        if (strncmp(line, "service", 7) == 0) {
            const char *q = strchr(line, '"');
            if (q) {
                sscanf(q, "\"%127[^\"]\"", cur_svc);
            }
            continue;
        }
        if (strncmp(line, "stack_id", 8) == 0 && cur_svc[0]) {
            const char *q = strchr(line, '"');
            char stack_id[32] = {0};
            if (q) {
                sscanf(q, "\"%31[^\"]\"", stack_id);
            }
            if (strcmp(cur_svc, svc) == 0) {
                strncpy(out, stack_id, out_len - 1);
                out[out_len - 1] = '\0';
                fclose(f);
                return 0;
            }
        }
    }
    fclose(f);
    return -1;
}

static void ledger_slug(const char *actor, char *slug, size_t slug_len) {
    const char *at = strchr(actor, '@');
    size_t n = at ? (size_t)(at - actor) : strlen(actor);
    if (n >= slug_len) {
        n = slug_len - 1;
    }
    memcpy(slug, actor, n);
    slug[n] = '\0';
    for (size_t i = 0; slug[i]; i++) {
        slug[i] = (char)tolower((unsigned char)slug[i]);
    }
}

static int plane_a_carryover(const char *slug, int *out) {
    char buf[8192];
    if (read_file(PLANE_A, buf, sizeof(buf)) < 0) {
        return -1;
    }
    const char *map = strstr(buf, "\"carryover\"");
    if (!map) {
        return -1;
    }
    map = strchr(map, '{');
    if (!map) {
        return -1;
    }
    char needle[96];
    snprintf(needle, sizeof(needle), "\"%s\"", slug);
    const char *hit = strstr(map, needle);
    if (!hit) {
        return -1;
    }
    const char *colon = strchr(hit, ':');
    if (!colon) {
        return -1;
    }
    *out = atoi(colon + 1);
    return 0;
}

int cfg_read_ledger_failures(const char *actor) {
    char slug[PL_NAME_MAX];
    ledger_slug(actor, slug, sizeof(slug));

    int from_plane = 0;
    if (plane_a_carryover(slug, &from_plane) == 0) {
        return from_plane;
    }

    char path[512];
    snprintf(path, sizeof(path), "%s/%s.tally", LEDGER_DIR, slug);
    FILE *f = fopen(path, "r");
    if (!f) {
        return 0;
    }
    char line[256];
    int failures = 0;
    while (fgets(line, sizeof(line), f)) {
        if (strncmp(line, "failures=", 9) == 0) {
            failures = atoi(line + 9);
        }
    }
    fclose(f);
    return failures;
}
