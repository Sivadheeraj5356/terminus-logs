#ifndef ROLE_SNAP_H
#define ROLE_SNAP_H

#include <stddef.h>
#include <stdint.h>

typedef enum {
    BK_NONE = 0,
    BK_A5 = 1,
    BK_U8 = 2
} BufKind;

#define RB_MAX 128
#define DCASE_ID 32
#define DCASE_MAX 8
#define HC_NAME 128
#define HC_LINE 256
#define NL_MAX 8

typedef struct {
    uint8_t bytes[RB_MAX];
    size_t len;
    char display[RB_MAX];
    BufKind kind;
    uint8_t wire_tag;
    uint32_t cap_bits;
} RoleSnap;

typedef struct {
    char items[NL_MAX][HC_NAME];
    int count;
} TokList;

#endif
