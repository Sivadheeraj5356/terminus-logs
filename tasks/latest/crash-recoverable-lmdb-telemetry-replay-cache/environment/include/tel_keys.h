#ifndef TEL_KEYS_H
#define TEL_KEYS_H

#include <stdint.h>

#define TEL_SAMPLES_DBI "samples"
#define TEL_ERRORS_DBI "errors"
#define TEL_RESTARTS_DBI "restarts"

#define TEL_SAMPLE_KEY_LEN 16
#define TEL_ERROR_KEY_LEN 12
#define TEL_RESTART_KEY_LEN 8

#define TEL_CORRELATION_WINDOW_NS 60000000000ULL

void tel_put_u64_be(uint8_t *out, uint64_t v);
uint64_t tel_read_u64_be(const uint8_t *in);
void tel_put_u32_be(uint8_t *out, uint32_t v);
uint32_t tel_read_u32_be(const uint8_t *in);
uint64_t tel_read_error_ts_key(const uint8_t *key_bytes);

#endif
