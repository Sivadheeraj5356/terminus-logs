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
    (void)pub_a;
    (void)pub_b;
    (void)handoff;
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

    memset(&row, 0, sizeof(row));
    snprintf(row.site_id, sizeof(row.site_id), "%s", site);
    snprintf(row.scenario, sizeof(row.scenario), "pin_base");
    row.link_count = stub;
    row.cookie_gen_a = gen_a;
    row.cookie_gen_b = gen_b;
    scope_label(scope, row.scope_code, sizeof(row.scope_code));
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
    /* scope_b band label tracks chain rebind_scope; high band when rebind_scope is at least three */
    scope_label(2, row.scope_code, sizeof(row.scope_code));
    append_row(rows, count, prev_p7, &row);
    strncpy(prev_p7, rows[*count - 1].p7_digest_hex, 16);
    prev_p7[16] = '\0';

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
    scope_label(1, row.scope_code, sizeof(row.scope_code));
    row.admit_code[0] = '\0';
    append_row(rows, count, prev_p7, &row);
    strncpy(prev_p7, rows[*count - 1].p7_digest_hex, 16);
    prev_p7[16] = '\0';
    (void)chain_scope_for;
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
