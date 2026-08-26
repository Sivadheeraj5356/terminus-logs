#ifndef POLICY_ROW_H
#define POLICY_ROW_H

typedef struct {
    char site_id[32];
    char scenario[24];
    int link_count;
    int cookie_gen_a;
    int cookie_gen_b;
    char scope_code[8];
    char admit_code[8];
    char p7_digest_hex[17];
    int rule_idx;
    int window_seq;
} policy_row_t;

#endif
