#include "tel_keys.h"

#include <string.h>

void tel_put_u64_be(uint8_t *out, uint64_t v) {
    for (int i = 0; i < 8; i++) {
        out[i] = (uint8_t)((v >> (56 - 8 * i)) & 0xff);
    }
}

uint64_t tel_read_u64_be(const uint8_t *in) {
    uint64_t v = 0;
    for (int i = 0; i < 8; i++) {
        v = (v << 8) | in[i];
    }
    return v;
}

void tel_put_u32_be(uint8_t *out, uint32_t v) {
    for (int i = 0; i < 4; i++) {
        out[i] = (uint8_t)((v >> (24 - 8 * i)) & 0xff);
    }
}

uint32_t tel_read_u32_be(const uint8_t *in) {
    uint32_t v = 0;
    for (int i = 0; i < 4; i++) {
        v = (v << 8) | in[i];
    }
    return v;
}

uint64_t tel_read_error_ts_key(const uint8_t *key_bytes) {
    return tel_read_u64_be(key_bytes + 4);
}
