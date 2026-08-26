#pragma once
#include "pamlink/types.h"
int run_tape_audit(const char *tape_path, const char *out_path, const char *conv_id,
                   const stack_table *stacks, const acct_table *accts, int deny);
