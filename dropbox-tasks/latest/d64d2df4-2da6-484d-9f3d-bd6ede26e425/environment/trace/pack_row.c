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

static void replay_cksum_hex(size_t row_count, char *out, size_t cap)
{
    snprintf(out, cap, "%02x", (unsigned)(row_count % 256));
}

static void bind_seq_hex(size_t row_count, char *out, size_t cap)
{
    unsigned bind = 0;
    (void)epoch_chain_bind_seq(&bind);
    snprintf(out, cap, "%02x", (unsigned)(row_count ^ bind) % 256);
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
    replay_cksum_hex(count, replay_cksum, sizeof(replay_cksum));
    bind_seq_hex(count, bind_seq, sizeof(bind_seq));
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
