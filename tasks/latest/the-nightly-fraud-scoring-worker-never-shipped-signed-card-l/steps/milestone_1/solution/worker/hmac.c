#include "hmac.h"

#include <openssl/evp.h>
#include <openssl/provider.h>
#include <stdio.h>
#include <string.h>

#define SHA256_DIGEST_LENGTH 32
#define SHA256_BLOCK_SIZE 64

static int crypto_ready = 0;

static int ensure_crypto(void) {
    if (crypto_ready) {
        return 0;
    }
    if (OSSL_PROVIDER_load(NULL, "default") == NULL) {
        return -1;
    }
    crypto_ready = 1;
    return 0;
}

static int sha256_digest(
    const unsigned char *data,
    size_t data_len,
    unsigned char *out
) {
    EVP_MD_CTX *ctx = NULL;
    EVP_MD *md = NULL;
    unsigned int out_len = 0;
    int rc = -1;

    ctx = EVP_MD_CTX_new();
    md = EVP_MD_fetch(NULL, "SHA2-256", NULL);
    if (ctx == NULL || md == NULL) {
        goto cleanup;
    }
    if (EVP_DigestInit_ex(ctx, md, NULL) != 1) {
        goto cleanup;
    }
    if (EVP_DigestUpdate(ctx, data, data_len) != 1) {
        goto cleanup;
    }
    if (EVP_DigestFinal_ex(ctx, out, &out_len) != 1) {
        goto cleanup;
    }
    rc = 0;

cleanup:
    EVP_MD_CTX_free(ctx);
    EVP_MD_free(md);
    return rc;
}

static int sha256_digest_two(
    const unsigned char *data1,
    size_t len1,
    const unsigned char *data2,
    size_t len2,
    unsigned char *out
) {
    EVP_MD_CTX *ctx = NULL;
    EVP_MD *md = NULL;
    unsigned int out_len = 0;
    int rc = -1;

    ctx = EVP_MD_CTX_new();
    md = EVP_MD_fetch(NULL, "SHA2-256", NULL);
    if (ctx == NULL || md == NULL) {
        goto cleanup;
    }
    if (EVP_DigestInit_ex(ctx, md, NULL) != 1) {
        goto cleanup;
    }
    if (EVP_DigestUpdate(ctx, data1, len1) != 1) {
        goto cleanup;
    }
    if (EVP_DigestUpdate(ctx, data2, len2) != 1) {
        goto cleanup;
    }
    if (EVP_DigestFinal_ex(ctx, out, &out_len) != 1) {
        goto cleanup;
    }
    rc = 0;

cleanup:
    EVP_MD_CTX_free(ctx);
    EVP_MD_free(md);
    return rc;
}

int hmac_sha256_hex(
    const char *secret,
    const char *message,
    char *out_hex,
    size_t out_hex_size
) {
    unsigned char key[SHA256_BLOCK_SIZE];
    unsigned char ipad[SHA256_BLOCK_SIZE];
    unsigned char opad[SHA256_BLOCK_SIZE];
    unsigned char inner_hash[SHA256_DIGEST_LENGTH];
    unsigned char outer_hash[SHA256_DIGEST_LENGTH];
    size_t secret_len;
    size_t msg_len;
    int i;

    if (out_hex_size < 65 || secret == NULL || message == NULL) {
        return -1;
    }
    if (ensure_crypto() != 0) {
        return -1;
    }

    secret_len = strlen(secret);
    msg_len = strlen(message);
    memset(key, 0, sizeof(key));

    if (secret_len > SHA256_BLOCK_SIZE) {
        if (sha256_digest((const unsigned char *)secret, secret_len, key) != 0) {
            return -1;
        }
    } else {
        memcpy(key, secret, secret_len);
    }

    for (i = 0; i < SHA256_BLOCK_SIZE; i++) {
        ipad[i] = (unsigned char)(key[i] ^ 0x36);
        opad[i] = (unsigned char)(key[i] ^ 0x5c);
    }

    if (sha256_digest_two(ipad, SHA256_BLOCK_SIZE, (const unsigned char *)message, msg_len, inner_hash)
        != 0) {
        return -1;
    }
    if (sha256_digest_two(opad, SHA256_BLOCK_SIZE, inner_hash, SHA256_DIGEST_LENGTH, outer_hash) != 0) {
        return -1;
    }

    for (i = 0; i < SHA256_DIGEST_LENGTH; i++) {
        sprintf(out_hex + (i * 2), "%02x", outer_hash[i]);
    }
    out_hex[SHA256_DIGEST_LENGTH * 2] = '\0';
    return 0;
}
