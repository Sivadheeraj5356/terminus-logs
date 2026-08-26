#ifndef GRANT_BUF_H
#define GRANT_BUF_H

#include <stdint.h>

typedef struct {
    uint32_t mask;
} GrantBuf;

typedef struct {
    uint32_t bits;
} CapSet;

typedef struct {
    uint32_t mask[4];
    int count;
} AcceptSnap;

#endif
