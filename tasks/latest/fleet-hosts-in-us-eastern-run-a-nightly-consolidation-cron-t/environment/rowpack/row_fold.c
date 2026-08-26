#include "row_fold.h"

#include <openssl/evp.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int fold_row(const char *day_key, int wall_off, int seq, int payload, packed_row *out) {
    if (!day_key || !out) {
        return -1;
    }
    memset(out, 0, sizeof(*out));
    strncpy(out->day_key, day_key, sizeof(out->day_key) - 1);
    out->wall_off = wall_off;
    out->seq = seq;
    out->payload = payload;
    return 0;
}

static int cmp_rows(const void *a, const void *b) {
    const packed_row *ra = a;
    const packed_row *rb = b;
    char la[128];
    char lb[128];
    snprintf(la, sizeof la, "%d,%s,%s,%d,%d,%d", ra->cyc, ra->pane, ra->day_key,
             ra->wall_off, ra->seq, ra->payload);
    snprintf(lb, sizeof lb, "%d,%s,%s,%d,%d,%d", rb->cyc, rb->pane, rb->day_key,
             rb->wall_off, rb->seq, rb->payload);
    return strcmp(la, lb);
}

int hash_rows(const packed_row *rows, int count, char *hex_out, size_t hex_cap) {
    if (!rows || count <= 0 || !hex_out || hex_cap < 65) {
        return -1;
    }
    packed_row *copy = calloc((size_t)count, sizeof(packed_row));
    if (!copy) {
        return -2;
    }
    memcpy(copy, rows, (size_t)count * sizeof(packed_row));
    qsort(copy, (size_t)count, sizeof(packed_row), cmp_rows);

    EVP_MD_CTX *ctx = EVP_MD_CTX_new();
    if (!ctx) {
        free(copy);
        return -3;
    }
    if (EVP_DigestInit_ex(ctx, EVP_sha256(), NULL) != 1) {
        EVP_MD_CTX_free(ctx);
        free(copy);
        return -4;
    }
    for (int i = 0; i < count; i++) {
        char line[256];
        snprintf(line, sizeof line, "%d,%s,%s,%d,%d,%d\n", copy[i].cyc, copy[i].pane,
                 copy[i].day_key, copy[i].wall_off, copy[i].seq, copy[i].payload);
        EVP_DigestUpdate(ctx, line, strlen(line));
    }
    unsigned char md[EVP_MAX_MD_SIZE];
    unsigned int md_len = 0;
    if (EVP_DigestFinal_ex(ctx, md, &md_len) != 1) {
        EVP_MD_CTX_free(ctx);
        free(copy);
        return -5;
    }
    EVP_MD_CTX_free(ctx);
    free(copy);
    for (unsigned int i = 0; i < md_len; i++) {
        snprintf(hex_out + (i * 2), 3, "%02x", md[i]);
    }
    hex_out[md_len * 2] = '\0';
    return 0;
}
