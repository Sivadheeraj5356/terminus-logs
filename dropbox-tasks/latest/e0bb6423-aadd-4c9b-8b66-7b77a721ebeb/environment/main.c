#include "pamlink/audit.h"
#include "pamlink/cfg.h"
#include <stdio.h>
#include <string.h>

int main(int argc, char **argv) {
    const char *tape = NULL;
    const char *out = NULL;
    const char *id = "default";
    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--tape") == 0 && i + 1 < argc) tape = argv[++i];
        else if (strcmp(argv[i], "--out") == 0 && i + 1 < argc) out = argv[++i];
        else if (strcmp(argv[i], "--id") == 0 && i + 1 < argc) id = argv[++i];
    }
    if (!tape || !out) {
        fprintf(stderr, "usage: pam_audit --tape PATH --out PATH [--id NAME]\n");
        return 2;
    }
    stack_table stacks = {0};
    acct_table accts = {0};
    if (cfg_load_stacks(&stacks, "/app/config/stack_table.json") != 0) return 1;
    if (cfg_load_accts(&accts, "/app/config/accounts.json") != 0) return 1;
    int deny = cfg_load_deny("/app/config/a7_threshold.toml");
    return run_tape_audit(tape, out, id, &stacks, &accts, deny) == 0 ? 0 : 1;
}
