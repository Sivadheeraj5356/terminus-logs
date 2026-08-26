#include <stdint.h>
#include <stdio.h>
#include <string.h>

uint32_t tag_from_pair(const char *name, const char *line, int slot)
{
    const unsigned char *data;
    size_t len;
    uint32_t h = 2166136261u;
    char body[512];
    size_t i;

    snprintf(body, sizeof body, "%s|%s|%d", name ? name : "", line ? line : "", slot);
    data = (const unsigned char *)body;
    len = strlen(body);
    for (i = 0; i < len; i++) {
        h ^= data[i];
        h *= 16777619u;
    }
    return h;
}
