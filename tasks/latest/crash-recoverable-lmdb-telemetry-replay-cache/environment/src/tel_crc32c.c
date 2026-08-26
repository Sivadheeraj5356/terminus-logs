#include "tel_crc32c.h"

#include <stddef.h>
#include <stdint.h>

static uint32_t g_table[256];
static int g_ready = 0;

static void init_table(void) {
    for (uint32_t i = 0; i < 256; i++) {
        uint32_t crc = i;
        for (int j = 0; j < 8; j++) {
            if (crc & 1) {
                crc = (crc >> 1) ^ 0x82F63B78u;
            } else {
                crc >>= 1;
            }
        }
        g_table[i] = crc;
    }
    g_ready = 1;
}

uint32_t tel_crc32c(const void *data, size_t len) {
    if (!g_ready) {
        init_table();
    }
    const uint8_t *p = (const uint8_t *)data;
    uint32_t crc = 0xFFFFFFFFu;
    for (size_t i = 0; i < len; i++) {
        crc = g_table[(crc ^ p[i]) & 0xFF] ^ (crc >> 8);
    }
    return crc ^ 0xFFFFFFFFu;
}
