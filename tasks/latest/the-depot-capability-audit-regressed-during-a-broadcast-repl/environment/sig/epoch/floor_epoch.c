#include "floor_epoch.h"

#include <stdio.h>
#include <string.h>

#define FLOOR_PATH "/app/environment/data/runtime/epoch_floor.json"

int floor_read_f(FloorState *out) {
    if (!out) {
        return -1;
    }
    memset(out, 0, sizeof(*out));
    FILE *fp = fopen(FLOOR_PATH, "r");
    if (!fp) {
        return -1;
    }
    char blob[256];
    size_t n = fread(blob, 1, sizeof(blob) - 1, fp);
    blob[n] = '\0';
    fclose(fp);
    const char *p = strstr(blob, "\"floor_epoch\"");
    if (!p) {
        return -1;
    }
    if (sscanf(strchr(p, ':') + 1, "%u", &out->floor_epoch) != 1) {
        return -1;
    }
    return 0;
}

int floor_epoch_ok(uint32_t ticket_epoch, uint32_t floor_epoch) {
    if (ticket_epoch < floor_epoch - 1) {
        return 0;
    }
    return 1;
}
