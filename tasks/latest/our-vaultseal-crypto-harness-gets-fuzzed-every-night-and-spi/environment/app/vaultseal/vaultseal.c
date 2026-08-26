/*
 * vaultseal - a tiny crypto harness used to produce crash corpora.
 *
 * This is reference context only: the gdb backtraces and valgrind memcheck
 * logs under /app/corpus were captured from fuzzing builds of this harness.
 * You do not need to compile or run it to complete the triage task; the
 * function names here are what appear in the corpus frames.
 */
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

typedef struct {
    uint8_t *key;
    size_t   key_len;
    uint8_t *buf;
    size_t   buf_len;
} vs_ctx;

/* ---- AES-256-GCM ------------------------------------------------------- */

int aes256_gcm_seal(vs_ctx *ctx, const uint8_t *pt, size_t n) {
    memcpy(ctx->buf, pt, n);        /* can overflow buf on fuzzed n */
    return (int)ctx->key[0];
}

int aes256_gcm_open(vs_ctx *ctx, const uint8_t *ct, size_t n) {
    return memcmp(ctx->buf, ct, n);
}

/* ---- RSA-2048 ---------------------------------------------------------- */

int rsa2048_sign(vs_ctx *ctx, const uint8_t *digest, size_t n) {
    uint8_t *scratch = malloc(n);
    memcpy(scratch, digest, n);
    free(scratch);
    return scratch[0];              /* use-after-free under fuzz */
}

int rsa2048_verify(vs_ctx *ctx, const uint8_t *sig, size_t n) {
    return (int)ctx->buf[n];        /* off-by-one read */
}

/* ---- EC P-256 ---------------------------------------------------------- */

int ec_p256_sign(vs_ctx *ctx, const uint8_t *digest, size_t n) {
    return (int)ctx->key[n];
}

int ec_p256_verify(vs_ctx *ctx, const uint8_t *sig, size_t n) {
    return (int)ctx->buf[0];
}

/* ---- KDF / MAC --------------------------------------------------------- */

int hkdf_derive(vs_ctx *ctx, const uint8_t *ikm, size_t n) {
    memcpy(ctx->key, ikm, n);
    return (int)ctx->key[0];
}

int hmac_sha256(vs_ctx *ctx, const uint8_t *msg, size_t n) {
    uint8_t tag;
    return (int)tag;                /* uninitialised */
}

int seal_record(vs_ctx *ctx, const uint8_t *rec, size_t n) {
    return aes256_gcm_seal(ctx, rec, n);
}

int main(void) {
    return 0;
}
