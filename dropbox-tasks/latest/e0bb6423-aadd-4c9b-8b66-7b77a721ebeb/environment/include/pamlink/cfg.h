#pragma once
#include <stddef.h>
#include "pamlink/types.h"

int cfg_load_stacks(stack_table *tbl, const char *path);
int cfg_load_accts(acct_table *tbl, const char *path);
int cfg_load_deny(const char *path);
int cfg_load_count_modules(char mods[][PL_NAME_MAX], int max, int *out_n);
int cfg_load_realm_mode(char *mode, size_t mode_len);
int cfg_lookup_stack_override(const char *svc, char *out, size_t out_len);
int cfg_read_ledger_failures(const char *actor);
