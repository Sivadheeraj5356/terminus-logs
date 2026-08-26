#pragma once
#include <stddef.h>
#include "pamlink/types.h"
int phase1_tally(const tape_event *ev, int n);
int phase2_expired(const char *actor, int64_t when, const acct_table *tbl);
int phase3_stack(const char *svc, const stack_table *tbl, char *out, size_t out_len);
void phase4_canon(const char *raw, char *out, size_t out_len);
int phase5_locked(int tally, int cap);
