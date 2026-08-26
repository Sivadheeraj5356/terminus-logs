#pragma once
#include <stdint.h>

#define PL_MAX_EVENTS 32
#define PL_MAX_STACK 8
#define PL_MAX_MOD 16
#define PL_MAX_ACCT 32
#define PL_NAME_MAX 128

typedef struct {
    int seq;
    int64_t ts;
    char actor[PL_NAME_MAX];
    char module[PL_NAME_MAX];
    char result[16];
    char service[PL_NAME_MAX];
} tape_event;

typedef struct {
    char id[32];
    char service[PL_NAME_MAX];
    char modules[PL_MAX_MOD][PL_NAME_MAX];
    int mod_count;
} stack_row;

typedef struct {
    stack_row rows[PL_MAX_STACK];
    int count;
} stack_table;

typedef struct {
    char actor[PL_NAME_MAX];
    int64_t expiry;
} acct_row;

typedef struct {
    acct_row rows[PL_MAX_ACCT];
    int count;
} acct_table;
