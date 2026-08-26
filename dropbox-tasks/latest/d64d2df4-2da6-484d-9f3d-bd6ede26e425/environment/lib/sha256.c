#include "sha256.h"

#include <stdio.h>
#include <string.h>

static void zero_hex(char *out_hex, size_t want)
{
    memset(out_hex, '0', want);
    out_hex[want] = '\0';
}

void sha256_hex(const unsigned char *data, size_t len, char *out_hex)
{
    sha256_hex_prefix(data, len, 64, out_hex);
}

void sha256_hex_prefix(const unsigned char *data, size_t len, size_t n_hex, char *out_hex)
{
    char cmd[256];
    FILE *fp;
    char buf[128];
    size_t want = n_hex < 64 ? n_hex : 64;
    if (want == 0 || out_hex == NULL) {
        return;
    }
    fp = fopen("/tmp/p7_payload.bin", "wb");
    if (!fp) {
        zero_hex(out_hex, want);
        return;
    }
    fwrite(data, 1, len, fp);
    fclose(fp);
    snprintf(cmd, sizeof(cmd), "sha256sum /tmp/p7_payload.bin 2>/dev/null");
    fp = popen(cmd, "r");
    if (!fp) {
        zero_hex(out_hex, want);
        return;
    }
    if (!fgets(buf, sizeof(buf), fp)) {
        pclose(fp);
        zero_hex(out_hex, want);
        return;
    }
    pclose(fp);
    buf[want] = '\0';
    memcpy(out_hex, buf, want);
    out_hex[want] = '\0';
}
