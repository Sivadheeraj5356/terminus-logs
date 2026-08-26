#include "pamlink/audit.h"
#include "pamlink/tapeio.h"
#include "pamlink/phase.h"
#include "sha256.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static const stack_row *find_stack(const stack_table *tbl, const char *id) {
    for (int i = 0; i < tbl->count; i++) {
        if (strcmp(tbl->rows[i].id, id) == 0) return &tbl->rows[i];
    }
    return NULL;
}

static int digest_hex_of(const char *payload, char *out, size_t out_len) {
    unsigned char hash[32];
    sha256((const unsigned char *)payload, strlen(payload), hash);
    if (out_len < 65) return -1;
    for (int i = 0; i < 32; i++) {
        sprintf(out + i * 2, "%02x", hash[i]);
    }
    out[64] = '\0';
    return 0;
}

static int cmp_bind_mod(const void *a, const void *b) {
    const char *ma = (const char *)a;
    const char *mb = (const char *)b;
    return strcmp(ma, mb);
}

int run_tape_audit(const char *tape_path, const char *out_path, const char *conv_id,
                   const stack_table *stacks, const acct_table *accts, int deny) {
    tape_event ev[PL_MAX_EVENTS];
    int n = 0;
    if (tape_read(tape_path, ev, PL_MAX_EVENTS, &n) != 0) return -1;
    int tally = phase1_tally(ev, n);
    char stack_id[32] = {0};
    phase3_stack(ev[n - 1].service, stacks, stack_id, sizeof(stack_id));
    const stack_row *sr = find_stack(stacks, stack_id);
    char canon[PL_NAME_MAX];
    phase4_canon(ev[0].actor, canon, sizeof(canon));
    int expired = phase2_expired(ev[0].actor, ev[0].ts, accts);
    int locked = phase5_locked(tally, deny);

    char mod_tags[PL_MAX_MOD][PL_NAME_MAX];
    int bound_flags[PL_MAX_MOD];
    char reasons[PL_MAX_MOD][16];
    int mod_n = 0;
    if (sr) {
        for (int m = 0; m < sr->mod_count && mod_n < PL_MAX_MOD; m++) {
            const char *mod = sr->modules[m];
            int found = 0;
            int ok = 0;
            for (int i = 0; i < n; i++) {
                if (strcmp(ev[i].module, mod) == 0) {
                    found = 1;
                    ok = strcmp(ev[i].result, "ok") == 0;
                    break;
                }
            }
            strncpy(mod_tags[mod_n], mod, PL_NAME_MAX - 1);
            mod_tags[mod_n][PL_NAME_MAX - 1] = '\0';
            bound_flags[mod_n] = found && ok;
            strncpy(reasons[mod_n], found ? (ok ? "ok" : "mismatch") : "missing", 15);
            reasons[mod_n][15] = '\0';
            mod_n++;
        }
        qsort(mod_tags, (size_t)mod_n, PL_NAME_MAX, cmp_bind_mod);
        for (int i = 0; i < mod_n; i++) {
            for (int m = 0; m < sr->mod_count; m++) {
                if (strcmp(mod_tags[i], sr->modules[m]) == 0) {
                    int found = 0;
                    int ok = 0;
                    for (int j = 0; j < n; j++) {
                        if (strcmp(ev[j].module, sr->modules[m]) == 0) {
                            found = 1;
                            ok = strcmp(ev[j].result, "ok") == 0;
                            break;
                        }
                    }
                    bound_flags[i] = found && ok;
                    strncpy(reasons[i], found ? (ok ? "ok" : "mismatch") : "missing", 15);
                    reasons[i][15] = '\0';
                    break;
                }
            }
        }
    }

    char payload[8192];
    size_t pos = 0;
    pos += (size_t)snprintf(payload + pos, sizeof(payload) - pos, "{\"binding_rows\":[");
    for (int i = 0; i < mod_n; i++) {
        if (i) pos += (size_t)snprintf(payload + pos, sizeof(payload) - pos, ",");
        pos += (size_t)snprintf(
            payload + pos, sizeof(payload) - pos,
            "{\"bound\":%s,\"canon_actor\":\"%s\",\"module_tag\":\"%s\",\"reason\":\"%s\"}",
            bound_flags[i] ? "true" : "false", canon, mod_tags[i], reasons[i]);
    }
    pos += (size_t)snprintf(
        payload + pos, sizeof(payload) - pos,
        "],\"conversation_id\":\"%s\",\"expired_account\":%s,\"lockout_active\":%s,"
        "\"retry_count\":%d,\"stack_binding\":\"%s\"}",
        conv_id, expired ? "true" : "false", locked ? "true" : "false", tally, stack_id);

    char digest[65];
    if (digest_hex_of(payload, digest, sizeof(digest)) != 0) return -1;

    FILE *f = fopen(out_path, "w");
    if (!f) return -1;
    fprintf(f, "%.*s,\"digest_hex\":\"%s\"}\n", (int)pos - 1, payload, digest);
    fclose(f);
    return 0;
}
