#include "digest.h"

#include <openssl/evp.h>
#include <openssl/hmac.h>
#include <string.h>

static void bytes_to_hex(const unsigned char *in, size_t n, char *out) {
    static const char *hex = "0123456789abcdef";
    for (size_t i = 0; i < n; i++) {
        out[i * 2] = hex[(in[i] >> 4) & 0x0f];
        out[i * 2 + 1] = hex[in[i] & 0x0f];
    }
    out[n * 2] = '\0';
}

int depot_sha256_hex(const unsigned char *data, size_t len, char *out_hex, size_t out_cap) {
    if (!data || !out_hex || out_cap < 65) {
        return -1;
    }
    unsigned char digest[EVP_MAX_MD_SIZE];
    unsigned int digest_len = 0;
    if (!EVP_Digest(data, len, digest, &digest_len, EVP_sha256(), NULL)) {
        return -1;
    }
    bytes_to_hex(digest, digest_len, out_hex);
    return 0;
}

int depot_hmac_sha256_hex(const unsigned char *key, size_t key_len, const unsigned char *msg,
                          size_t msg_len, char *out_hex, size_t out_cap) {
    if (!key || !msg || !out_hex || out_cap < 65) {
        return -1;
    }
    unsigned char digest[EVP_MAX_MD_SIZE];
    unsigned int digest_len = 0;
    if (!HMAC(EVP_sha256(), key, (int)key_len, msg, msg_len, digest, &digest_len)) {
        return -1;
    }
    bytes_to_hex(digest, digest_len, out_hex);
    return 0;
}
