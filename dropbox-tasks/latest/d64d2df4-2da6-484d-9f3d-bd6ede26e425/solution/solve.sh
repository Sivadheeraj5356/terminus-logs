#!/usr/bin/env bash
set -euo pipefail

cat > /app/environment/lib/chain_seed.c <<'GEOF'
#include "chain_seed.h"

#include "epoch_chain.h"

int chain_seed_for_site(const char *site, int link_inv, int rebind_epoch)
{
    (void)link_inv;
    return epoch_chain_seed(site, rebind_epoch);
}
GEOF

cat > /app/environment/lib/witness_gate.c <<'GEOF'
#include "witness_gate.h"

#include "epoch_chain.h"

#include <stdio.h>
#include <string.h>

#define WITNESS_PATH "/app/work/policy/replay.witness"

static int triangulation_byte(int scope, int pub_a, int pub_b, int handoff)
{
    return (scope ^ pub_a ^ pub_b ^ handoff) % 256;
}

static int witness_byte_for_site(const char *site, int *byte_out)
{
    int scope = 0;
    int pub_a = 0;
    int pub_b = 0;
    int handoff = 0;

    if (byte_out == NULL) {
        return -1;
    }
    if (epoch_chain_read(site, &scope, &pub_a, &pub_b, &handoff) != 0) {
        return -1;
    }
    *byte_out = triangulation_byte(scope, pub_a, pub_b, handoff);
    return 0;
}

static int upsert_witness_row(const char *site, int byte)
{
    FILE *in = fopen(WITNESS_PATH, "r");
    FILE *out = fopen(WITNESS_PATH ".tmp", "w");
    char line[128];
    char s[32];
    unsigned stored = 0;
    int found = 0;

    if (!out) {
        if (in) {
            fclose(in);
        }
        return -1;
    }
    if (in) {
        while (fgets(line, sizeof(line), in)) {
            if (sscanf(line, "%31s %x", s, &stored) != 2) {
                continue;
            }
            if (strcmp(s, site) == 0) {
                fprintf(out, "%s\t%02x\n", site, (unsigned)byte % 256U);
                found = 1;
            } else {
                fputs(line, out);
            }
        }
        fclose(in);
    }
    if (!found) {
        fprintf(out, "%s\t%02x\n", site, (unsigned)byte % 256U);
    }
    fclose(out);
    remove(WITNESS_PATH);
    rename(WITNESS_PATH ".tmp", WITNESS_PATH);
    return 0;
}

int witness_refresh_site(const char *site)
{
    int byte = 0;

    if (site == NULL) {
        return -1;
    }
    if (witness_byte_for_site(site, &byte) != 0) {
        return -1;
    }
    return upsert_witness_row(site, byte);
}

int witness_refresh_all(void)
{
    const char *sites[] = {"site_j4", "site_p7"};
    size_t i;

    for (i = 0; i < sizeof(sites) / sizeof(sites[0]); i++) {
        if (witness_refresh_site(sites[i]) != 0) {
            return -1;
        }
    }
    return 0;
}

int witness_verify_emit(void)
{
    FILE *fp = fopen(WITNESS_PATH, "r");
    char line[128];
    char site[32];
    unsigned stored = 0;

    if (!fp) {
        return -1;
    }
    while (fgets(line, sizeof(line), fp)) {
        if (sscanf(line, "%31s %x", site, &stored) != 2) {
            continue;
        }
        int want = 0;
        if (witness_byte_for_site(site, &want) != 0) {
            fclose(fp);
            return -1;
        }
        if ((unsigned)want % 256U != stored % 256U) {
            fclose(fp);
            return -1;
        }
    }
    fclose(fp);
    return 0;
}
GEOF

cat > /app/environment/u4_pin/pin_core.c <<'GEOF'
#include <string.h>

int op_u4(const char *tier_tag, int link_cap, const char *ns_token, int *link_out, int *epoch_out)
{
    (void)tier_tag;
    *link_out = link_cap;
    *epoch_out = 1;
    if (tier_tag && strcmp(tier_tag, "paired") == 0) {
        *link_out = link_cap;
    }
    if (ns_token && strstr(ns_token, "ns_gen_b")) {
        *epoch_out = 3;
    } else if (ns_token && strstr(ns_token, "ns_gen_a")) {
        *epoch_out = 1;
    }
    return 0;
}
GEOF

cat > /app/environment/m1_key/key_pub.c <<'GEOF'
#include <stddef.h>
#include <stdio.h>
#include <string.h>

void lane_clear(void)
{
}

void lane_advance(unsigned gen_a, unsigned gen_b)
{
    (void)gen_a;
    (void)gen_b;
}

int carry_from_prior(const char *prior_site, int *carry_out)
{
    FILE *fp = fopen("/app/work/policy/m1.state", "r");
    char site[32];
    int gen_a = 0;
    int gen_b = 0;

    if (!fp || carry_out == NULL) {
        return -1;
    }
    *carry_out = 0;
    while (fscanf(fp, "%31s %d %d", site, &gen_a, &gen_b) == 3) {
        if (strcmp(site, prior_site) == 0) {
            *carry_out = (gen_a + gen_b) % 256;
            fclose(fp);
            return 0;
        }
    }
    fclose(fp);
    return -1;
}

int reconcile_m1(unsigned gen_id, int lane_index, const unsigned char *rule_blob, size_t blob_len,
                 int *map_out)
{
    unsigned acc = 0;
    size_t i;
    size_t lim = blob_len;
    if (lim > 8) {
        lim = 8;
    }
    for (i = 0; i < lim; i++) {
        acc = (acc + (unsigned)(rule_blob[i] ^ (unsigned char)gen_id)) % 256;
    }
    acc = (acc + (unsigned)(lane_index * (int)gen_id)) % 256;
    *map_out = (int)acc;
    return 0;
}
GEOF

cat > /app/environment/q3_probe/admit_gate.c <<'GEOF'
#include <string.h>

const char *host_admit(int scope, int link, int cap)
{
    if (scope == 3 && link == cap) {
        return "P0";
    }
    return "P8";
}

const char *work_admit(const char *handoff, int scope)
{
    if (handoff && strcmp(handoff, "arr3") == 0 && scope == 3) {
        return "P1";
    }
    return "P9";
}
GEOF

cat > /app/environment/q3_probe/admit_run.c <<'GEOF'
#include "admit_gate.c"

#include "../lib/epoch_chain.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int read_scope(const char *site, int *scope_out)
{
    FILE *fp = fopen("/app/work/policy/u4.state", "r");
    char s[32];
    int link = 0;
    int scope = 0;

    if (!fp) {
        return -1;
    }
    while (fscanf(fp, "%31s %d %d", s, &link, &scope) == 3) {
        if (strcmp(s, site) == 0) {
            *scope_out = scope;
            fclose(fp);
            return 0;
        }
    }
    fclose(fp);
    return -1;
}

static int read_link(const char *site, int *link_out)
{
    FILE *fp = fopen("/app/work/policy/u4.state", "r");
    char s[32];
    int link = 0;
    int scope = 0;

    if (!fp) {
        return -1;
    }
    while (fscanf(fp, "%31s %d %d", s, &link, &scope) == 3) {
        if (strcmp(s, site) == 0) {
            *link_out = link;
            fclose(fp);
            return 0;
        }
    }
    fclose(fp);
    return -1;
}

static int read_handoff_state(const char *site, char *out, size_t cap)
{
    FILE *fp = fopen("/app/work/policy/p5.state", "r");
    char s[32];
    char handoff[32];

    if (!fp) {
        return -1;
    }
    while (fscanf(fp, "%31s %31s", s, handoff) == 2) {
        if (strcmp(s, site) == 0) {
            snprintf(out, cap, "%s", handoff);
            fclose(fp);
            return 0;
        }
    }
    fclose(fp);
    return -1;
}

static const char *handoff_from_ord(int ord)
{
    if (ord == 1) {
        return "arr1";
    }
    if (ord == 2) {
        return "arr2";
    }
    if (ord == 3) {
        return "arr3";
    }
    return NULL;
}

static int read_handoff_chain(const char *site, char *out, size_t cap)
{
    int scope = 0;
    int pub_a = 0;
    int pub_b = 0;
    int ord = 0;
    const char *tok;

    if (epoch_chain_read(site, &scope, &pub_a, &pub_b, &ord) != 0 || ord <= 0) {
        return -1;
    }
    tok = handoff_from_ord(ord);
    if (tok == NULL) {
        return -1;
    }
    snprintf(out, cap, "%s", tok);
    return 0;
}

static int read_handoff(const char *site, char *out, size_t cap)
{
    if (read_handoff_chain(site, out, cap) == 0) {
        return 0;
    }
    return read_handoff_state(site, out, cap);
}

int main(int argc, char **argv)
{
    const char *site = NULL;
    const char *mode = NULL;
    char handoff[32];
    int scope = 0;
    int link = 0;
    int cap = 0;
    const char *code;

    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--site") == 0 && i + 1 < argc) {
            site = argv[++i];
        } else if (strcmp(argv[i], "--mode") == 0 && i + 1 < argc) {
            mode = argv[++i];
        } else if (strcmp(argv[i], "--cap") == 0 && i + 1 < argc) {
            cap = atoi(argv[++i]);
        }
    }
    if (site == NULL || mode == NULL) {
        fprintf(stderr, "usage: admit_run --site SITE --mode host|work [--cap N]\n");
        return 2;
    }
    if (read_scope(site, &scope) != 0) {
        return 1;
    }
    if (strcmp(mode, "host") == 0) {
        if (read_link(site, &link) != 0) {
            return 1;
        }
        code = host_admit(scope, link, cap);
    } else if (strcmp(mode, "work") == 0) {
        if (read_handoff(site, handoff, sizeof(handoff)) != 0) {
            return 1;
        }
        code = work_admit(handoff, scope);
    } else {
        fprintf(stderr, "unknown mode: %s\n", mode);
        return 2;
    }
    printf("%s\n", code);
    return 0;
}
GEOF

cat > /app/environment/d0/stg_u4.c <<'GEOF'
#include "../u4_pin/pin_core.c"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "../lib/chain_seed.h"
#include "../lib/epoch_chain.h"
#include "../lib/parse_tok.h"

int main(int argc, char **argv)
{
    const char *env_path = NULL;
    char site[32];
    char handle[64];
    char tag[32];
    char cap_str[16];
    int cap = 0;
    int link = 0;
    int epoch = 0;
    FILE *fp;

    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--env") == 0 && i + 1 < argc) {
            env_path = argv[++i];
        }
    }
    if (env_path == NULL) {
        fprintf(stderr, "usage: stg_u4 --env PATH\n");
        return 2;
    }
    if (pp_env_value(env_path, "SITE", site, sizeof(site)) != 0 ||
        pp_env_value(env_path, "NS_HANDLE", handle, sizeof(handle)) != 0 ||
        pp_env_value(env_path, "TIER_TAG", tag, sizeof(tag)) != 0 ||
        pp_env_value(env_path, "LINK_CAP", cap_str, sizeof(cap_str)) != 0) {
        return 1;
    }
    cap = atoi(cap_str);
    if (op_u4(tag, cap, handle, &link, &epoch) != 0) {
        return 1;
    }
    fp = fopen("/app/work/policy/u4.state", "a");
    if (!fp) {
        return 1;
    }
    fprintf(fp, "%s\t%d\t%d\n", site, link, epoch);
    fclose(fp);
    if (chain_seed_for_site(site, link, epoch) != 0) {
        return 1;
    }
    return 0;
}
GEOF

cat > /app/environment/d0/stg_m1.c <<'GEOF'
#include "../m1_key/key_pub.c"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "../lib/epoch_chain.h"
#include "../lib/parse_tok.h"

static int read_epoch_file(const char *path, unsigned *out)
{
    char val[32];
    if (pp_env_value(path, "GEN_ID", val, sizeof(val)) != 0) {
        return -1;
    }
    *out = (unsigned)atoi(val);
    return 0;
}

static int read_blob(unsigned char *buf, size_t cap, size_t *len)
{
    FILE *fp = fopen("/app/environment/fixtures/rule_seed.dat", "rb");
    size_t n;
    if (!fp) {
        return -1;
    }
    n = fread(buf, 1, cap, fp);
    fclose(fp);
    *len = n;
    return n > 0 ? 0 : -1;
}

static int read_tick(void)
{
    FILE *fp = fopen("/app/work/policy/window.tick", "r");
    int tick = 0;
    if (!fp) {
        return 0;
    }
    if (fscanf(fp, "%d", &tick) != 1) {
        tick = 0;
    }
    fclose(fp);
    return tick;
}

int main(int argc, char **argv)
{
    const char *env_path = NULL;
    char site[32];
    char if_str[16];
    char slots_str[16];
    unsigned ns_gen_a = 0;
    unsigned ns_gen_b = 0;
    unsigned char blob[256];
    size_t blob_len = 0;
    int if_index = 0;
    int slots = 0;
    int tick = 0;
    int lane = 0;
    int carry = 0;
    int gen_a = 0;
    int gen_b = 0;
    FILE *fp;

    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--env") == 0 && i + 1 < argc) {
            env_path = argv[++i];
        }
    }
    if (env_path == NULL) {
        fprintf(stderr, "usage: stg_m1 --env PATH\n");
        return 2;
    }
    if (pp_env_value(env_path, "SITE", site, sizeof(site)) != 0 ||
        pp_env_value(env_path, "IF_INDEX", if_str, sizeof(if_str)) != 0 ||
        pp_env_value(env_path, "RULE_SLOTS", slots_str, sizeof(slots_str)) != 0 ||
        read_epoch_file("/app/environment/fixtures/ns_gen_a.txt", &ns_gen_a) != 0 ||
        read_epoch_file("/app/environment/fixtures/ns_gen_b.txt", &ns_gen_b) != 0 ||
        read_blob(blob, sizeof(blob), &blob_len) != 0) {
        return 1;
    }
    if_index = atoi(if_str);
    slots = atoi(slots_str);
    tick = read_tick();
    lane_clear();
    lane = if_index;
    if (strcmp(site, "site_p7") == 0) {
        if (carry_from_prior("site_j4", &carry) != 0) {
            carry = 0;
        }
        lane += carry;
        if (tick > 0) {
            lane += tick % 16;
        }
    }
    if ((size_t)slots < blob_len) {
        blob_len = (size_t)slots;
    }
    if (reconcile_m1(ns_gen_a, lane, blob, blob_len, &gen_a) != 0 ||
        reconcile_m1(ns_gen_b, lane, blob, blob_len, &gen_b) != 0) {
        return 1;
    }
    lane_advance((unsigned)gen_a, (unsigned)gen_b);
    if (epoch_chain_publish(site, gen_a, gen_b) != 0) {
        return 1;
    }
    fp = fopen("/app/work/policy/m1.state", "a");
    if (!fp) {
        return 1;
    }
    fprintf(fp, "%s\t%d\t%d\n", site, gen_a, gen_b);
    fclose(fp);
    return 0;
}
GEOF

cat > /app/environment/d0/stg_p5.c <<'GEOF'
#include "../p5_hand/hand_run.c"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "../lib/epoch_chain.h"
#include "../lib/parse_tok.h"

static int read_pin_scope(const char *site, int *scope_out)
{
    FILE *fp = fopen("/app/work/policy/u4.state", "r");
    char s[32];
    int link = 0;
    int scope = 0;

    if (!fp) {
        return -1;
    }
    while (fscanf(fp, "%31s %d %d", s, &link, &scope) == 3) {
        if (strcmp(s, site) == 0) {
            *scope_out = scope;
            fclose(fp);
            return 0;
        }
    }
    fclose(fp);
    return -1;
}

int main(int argc, char **argv)
{
    const char *env_path = NULL;
    char site[32];
    char epoch[32];
    char inherit_str[8];
    char phase[16];
    char handoff[32];
    int inherit = 0;
    int pin_scope = 0;
    FILE *fp;

    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--env") == 0 && i + 1 < argc) {
            env_path = argv[++i];
        }
    }
    if (env_path == NULL) {
        fprintf(stderr, "usage: stg_p5 --env PATH\n");
        return 2;
    }
    if (pp_env_value(env_path, "SITE", site, sizeof(site)) != 0 ||
        pp_env_value(env_path, "NS_EPOCH", epoch, sizeof(epoch)) != 0 ||
        pp_env_value(env_path, "INHERIT_ARR", inherit_str, sizeof(inherit_str)) != 0) {
        return 1;
    }
    inherit = atoi(inherit_str);
    if (read_pin_scope(site, &pin_scope) != 0) {
        pin_scope = 0;
    }
    snprintf(phase, sizeof(phase), "inh%d", inherit);
    if (gate_p5(phase, site, inherit, pin_scope, handoff, sizeof(handoff)) != 0) {
        return 1;
    }
    if (epoch_chain_handoff(site, epoch_chain_handoff_from_token(handoff)) != 0) {
        return 1;
    }
    if (epoch_chain_scope_sync(site, pin_scope) != 0) {
        return 1;
    }
    fp = fopen("/app/work/policy/p5.state", "a");
    if (!fp) {
        return 1;
    }
    fprintf(fp, "%s\t%s\n", site, handoff);
    fclose(fp);
    return 0;
}
GEOF

cat > /app/environment/p5_hand/hand_run.c <<'GEOF'
#include <stdio.h>
#include <string.h>

int gate_p5(const char *epoch_id, const char *site_id, int inherit_arr, int pin_scope,
            char *handoff_out, size_t handoff_cap)
{
    (void)epoch_id;
    if (inherit_arr == 0) {
        snprintf(handoff_out, handoff_cap, "arr1");
        return 0;
    }
    if (site_id && strcmp(site_id, "site_p7") == 0 && pin_scope >= 3) {
        snprintf(handoff_out, handoff_cap, "arr3");
        return 0;
    }
    snprintf(handoff_out, handoff_cap, "arr2");
    return 0;
}
GEOF

cat > /app/environment/d0/assemble.c <<'GEOF'
#include "policy_row.h"
#include "../lib/epoch_chain.h"
#include "../lib/parse_tok.h"
#include "../lib/sha256.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int read_u4(const char *site, int *stub, int *scope)
{
    FILE *fp = fopen("/app/work/policy/u4.state", "r");
    char s[32];
    int a = 0;
    int sc = 0;
    if (!fp) {
        return -1;
    }
    while (fscanf(fp, "%31s %d %d", s, &a, &sc) == 3) {
        if (strcmp(s, site) == 0) {
            *stub = a;
            *scope = sc;
            fclose(fp);
            return 0;
        }
    }
    fclose(fp);
    return -1;
}

static int read_m1(const char *site, int *gen_a, int *gen_b)
{
    FILE *fp = fopen("/app/work/policy/m1.state", "r");
    char s[32];
    int a = 0;
    int b = 0;
    if (!fp) {
        return -1;
    }
    while (fscanf(fp, "%31s %d %d", s, &a, &b) == 3) {
        if (strcmp(s, site) == 0) {
            *gen_a = a;
            *gen_b = b;
            fclose(fp);
            return 0;
        }
    }
    fclose(fp);
    return -1;
}

static int read_probe(const char *site, const char *kind, char *code, size_t cap)
{
    char path[256];
    FILE *fp;
    snprintf(path, sizeof(path), "/app/work/policy/probe_%s_%s.txt", site, kind);
    fp = fopen(path, "r");
    if (!fp) {
        return -1;
    }
    if (!fgets(code, (int)cap, fp)) {
        fclose(fp);
        return -1;
    }
    code[strcspn(code, "\n")] = '\0';
    fclose(fp);
    return 0;
}

static void scope_label(int scope_num, char *out, size_t cap)
{
    snprintf(out, cap, "S%d", scope_num);
}

static void p7_material(const policy_row_t *r, char *buf, size_t cap)
{
    snprintf(buf, cap, "%d|%d|%d|%s|%d", r->link_count, r->cookie_gen_a, r->cookie_gen_b, r->scope_code,
             r->rule_idx);
}

static void p7_roll(const char *prev, const policy_row_t *r, char *out)
{
    char mat[128];
    char payload[256];
    p7_material(r, mat, sizeof(mat));
    if (prev[0]) {
        snprintf(payload, sizeof(payload), "%s%s", prev, mat);
    } else {
        snprintf(payload, sizeof(payload), "%s", mat);
    }
    sha256_hex_prefix((const unsigned char *)payload, strlen(payload), 16, out);
}

static int rule_idx_for(const char *env_path)
{
    char slots[32];
    if (pp_env_value(env_path, "RULE_SLOTS", slots, sizeof(slots)) != 0) {
        return 0;
    }
    return atoi(slots);
}

static int chain_scope_for(const char *site, int fallback)
{
    int chain_scope = 0;
    int pub_a = 0;
    int pub_b = 0;
    int handoff = 0;
    if (epoch_chain_read(site, &chain_scope, &pub_a, &pub_b, &handoff) == 0 && chain_scope > 0) {
        return chain_scope;
    }
    return fallback;
}

static int append_row(policy_row_t *rows, size_t *count, const char *prev_p7, const policy_row_t *src)
{
    policy_row_t *r = &rows[*count];
    *r = *src;
    r->window_seq = (int)*count;
    p7_roll(prev_p7, r, r->p7_digest_hex);
    (*count)++;
    return 0;
}

static int build_site(const char *env_path, policy_row_t *rows, size_t *count, char *prev_p7)
{
    char site[32];
    int stub = 0;
    int scope = 0;
    int chain_scope = 0;
    int gen_a = 0;
    int gen_b = 0;
    char admit[8];
    policy_row_t row;

    if (pp_env_value(env_path, "SITE", site, sizeof(site)) != 0) {
        return -1;
    }
    if (read_u4(site, &stub, &scope) != 0 || read_m1(site, &gen_a, &gen_b) != 0) {
        return -1;
    }
    chain_scope = chain_scope_for(site, scope);

    memset(&row, 0, sizeof(row));
    snprintf(row.site_id, sizeof(row.site_id), "%s", site);
    snprintf(row.scenario, sizeof(row.scenario), "pin_base");
    row.link_count = stub;
    row.cookie_gen_a = gen_a;
    row.cookie_gen_b = gen_b;
    scope_label(chain_scope, row.scope_code, sizeof(row.scope_code));
    row.rule_idx = rule_idx_for(env_path);
    row.admit_code[0] = '\0';
    append_row(rows, count, prev_p7, &row);
    strncpy(prev_p7, rows[*count - 1].p7_digest_hex, 16);
    prev_p7[16] = '\0';

    snprintf(row.scenario, sizeof(row.scenario), "map_row");
    append_row(rows, count, prev_p7, &row);
    strncpy(prev_p7, rows[*count - 1].p7_digest_hex, 16);

    snprintf(row.scenario, sizeof(row.scenario), "scope_a");
    scope_label(1, row.scope_code, sizeof(row.scope_code));
    append_row(rows, count, prev_p7, &row);
    strncpy(prev_p7, rows[*count - 1].p7_digest_hex, 16);

    snprintf(row.scenario, sizeof(row.scenario), "scope_b");
    if (chain_scope >= 3) {
        scope_label(3, row.scope_code, sizeof(row.scope_code));
    } else {
        scope_label(2, row.scope_code, sizeof(row.scope_code));
    }
    append_row(rows, count, prev_p7, &row);
    strncpy(prev_p7, rows[*count - 1].p7_digest_hex, 16);

    snprintf(row.scenario, sizeof(row.scenario), "probe_h");
    scope_label(scope, row.scope_code, sizeof(row.scope_code));
    if (read_probe(site, "host", admit, sizeof(admit)) == 0) {
        snprintf(row.admit_code, sizeof(row.admit_code), "%s", admit);
    }
    append_row(rows, count, prev_p7, &row);
    strncpy(prev_p7, rows[*count - 1].p7_digest_hex, 16);

    snprintf(row.scenario, sizeof(row.scenario), "probe_w");
    if (read_probe(site, "work", admit, sizeof(admit)) == 0) {
        snprintf(row.admit_code, sizeof(row.admit_code), "%s", admit);
    }
    append_row(rows, count, prev_p7, &row);
    strncpy(prev_p7, rows[*count - 1].p7_digest_hex, 16);

    snprintf(row.scenario, sizeof(row.scenario), "cross_row");
    scope_label(chain_scope, row.scope_code, sizeof(row.scope_code));
    row.admit_code[0] = '\0';
    append_row(rows, count, prev_p7, &row);
    strncpy(prev_p7, rows[*count - 1].p7_digest_hex, 16);
    prev_p7[16] = '\0';
    return 0;
}

static int write_ledger(const policy_row_t *rows, size_t count)
{
    FILE *fp = fopen("/app/work/policy/ledger.tsv", "w");
    size_t i;
    if (!fp) {
        return -1;
    }
    for (i = 0; i < count; i++) {
        const policy_row_t *r = &rows[i];
        fprintf(fp, "%s\t%s\t%d\t%d\t%d\t%s\t%s\t%s\t%d\t%d\n", r->site_id, r->scenario, r->link_count,
                r->cookie_gen_a, r->cookie_gen_b, r->scope_code, r->admit_code[0] ? r->admit_code : "-",
                r->p7_digest_hex, r->rule_idx, r->window_seq);
    }
    fclose(fp);
    return 0;
}

int main(int argc, char **argv)
{
    policy_row_t rows[32];
    size_t count = 0;
    char prev_p7[17] = "";

    if (argc >= 2 && strcmp(argv[1], "--assemble") == 0) {
        if (build_site("/app/environment/fixtures/site_j4.env", rows, &count, prev_p7) != 0) {
            return 1;
        }
        if (build_site("/app/environment/fixtures/site_p7.env", rows, &count, prev_p7) != 0) {
            return 1;
        }
        return write_ledger(rows, count) == 0 ? 0 : 1;
    }
    fprintf(stderr, "usage: j4_assemble --assemble\n");
    return 2;
}
GEOF

cat > /app/environment/trace/pack_row.c <<'PACK'
#include "../d0/policy_row.h"
#include "../lib/epoch_chain.h"
#include "../lib/witness_gate.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int read_ledger(policy_row_t *rows, size_t cap, size_t *count)
{
    FILE *fp = fopen("/app/work/policy/ledger.tsv", "r");
    char line[512];
    *count = 0;
    if (!fp) {
        return -1;
    }
    while (fgets(line, sizeof(line), fp) && *count < cap) {
        policy_row_t *r = &rows[*count];
        char admit[16];
        int n = sscanf(line, "%31s %23s %d %d %d %7s %15s %16s %d %d", r->site_id, r->scenario,
                       &r->link_count, &r->cookie_gen_a, &r->cookie_gen_b, r->scope_code, admit,
                       r->p7_digest_hex, &r->rule_idx, &r->window_seq);
        if (n < 10) {
            continue;
        }
        if (strcmp(admit, "-") == 0) {
            r->admit_code[0] = '\0';
        } else {
            snprintf(r->admit_code, sizeof(r->admit_code), "%s", admit);
        }
        (*count)++;
    }
    fclose(fp);
    return *count > 0 ? 0 : -1;
}

static void replay_cksum_hex(const policy_row_t *rows, size_t count, char *out, size_t cap)
{
    unsigned acc = 0;
    size_t i;
    for (i = 0; i < count; i++) {
        acc ^= (unsigned)rows[i].window_seq;
    }
    snprintf(out, cap, "%02x", acc % 256);
}

static void bind_seq_hex(char *out, size_t cap)
{
    unsigned bind = 0;
    if (epoch_chain_bind_seq(&bind) != 0) {
        bind = 0;
    }
    snprintf(out, cap, "%02x", bind % 256);
}

int pack_p7(const char *out_path, const void *rows_in, size_t row_count, size_t row_stride)
{
    policy_row_t rows[32];
    size_t count = 0;
    size_t i;
    FILE *fp;
    char replay_cksum[8];
    char bind_seq[8];
    (void)rows_in;
    (void)row_count;
    (void)row_stride;

    if (read_ledger(rows, 32, &count) != 0) {
        return -1;
    }
    if (witness_verify_emit() != 0) {
        return -1;
    }
    replay_cksum_hex(rows, count, replay_cksum, sizeof(replay_cksum));
    bind_seq_hex(bind_seq, sizeof(bind_seq));
    fp = fopen(out_path, "w");
    if (!fp) {
        return -1;
    }
    fprintf(fp, "{\n  \"rows\": [\n");
    for (i = 0; i < count; i++) {
        policy_row_t *r = &rows[i];
        fprintf(fp,
                "    {\"site_id\":\"%s\",\"scenario\":\"%s\",\"link_count\":%d,"
                "\"cookie_gen_a\":%d,\"cookie_gen_b\":%d,\"scope_code\":\"%s\",",
                r->site_id, r->scenario, r->link_count, r->cookie_gen_a, r->cookie_gen_b,
                r->scope_code);
        if (r->admit_code[0]) {
            fprintf(fp, "\"admit_code\":\"%s\",", r->admit_code);
        } else {
            fprintf(fp, "\"admit_code\":null,");
        }
        fprintf(fp, "\"p7_digest_hex\":\"%s\",\"rule_idx\":%d,\"window_seq\":%d}%s\n",
                r->p7_digest_hex, r->rule_idx, r->window_seq, (i + 1 < count) ? "," : "");
    }
    fprintf(fp,
            "  ],\n  \"summary\": {\"row_count\": %zu, \"trace_stamp\": \"policy-v1\", "
            "\"replay_cksum\": \"%s\", \"bind_seq\": \"%s\"}\n}\n",
            count, replay_cksum, bind_seq);
    fclose(fp);
    return 0;
}

#ifdef P7_EMIT_MAIN
int main(int argc, char **argv)
{
    const char *out = "/app/output/observ_trace.json";
    if (argc >= 3 && strcmp(argv[1], "--out") == 0) {
        out = argv[2];
    }
    return pack_p7(out, NULL, 0, 0) == 0 ? 0 : 1;
}
#endif
PACK

sed -i 's/tick = (scope + handoff) % 16;/tick = (scope + pub_a + pub_b + handoff) % 16;/' /app/environment/lib/epoch_chain.c

make -C /app/environment all

rm -f /app/output/observ_trace.json
mkdir -p /app/work/policy /app/output

/app/environment/tools/j4_round --round
/app/environment/tools/p7_emit --out /app/output/observ_trace.json

test -s /app/output/observ_trace.json
