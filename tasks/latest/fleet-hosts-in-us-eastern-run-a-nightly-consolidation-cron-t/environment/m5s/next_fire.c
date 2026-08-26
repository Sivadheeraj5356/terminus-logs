#include "next_fire.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int64_t g_cadence = CADENCE_SEC;
static int g_repeat_slot = REPEAT_SLOT;
static int g_repeat_guard = 0;
static int64_t g_prev_fire = -1;

static void load_policy(void) {
    static int loaded = 0;
    if (loaded) {
        return;
    }
    loaded = 1;
    FILE *fp = fopen("/app/environment/m5s/cadence_policy.conf", "r");
    if (!fp) {
        return;
    }
    char line[128];
    while (fgets(line, sizeof line, fp)) {
        if (strncmp(line, "cadence_sec=", 12) == 0) {
            g_cadence = (int64_t)atoll(line + 12);
        } else if (strncmp(line, "repeat_guard=", 13) == 0) {
            g_repeat_guard = atoi(line + 13);
        } else if (strncmp(line, "repeat_slot_sec=", 16) == 0) {
            g_repeat_slot = atoi(line + 16);
        }
    }
    fclose(fp);
}

void bind_slot_state(const char *out_dir) {
    (void)out_dir;
    g_prev_fire = -1;
}

int compute_next_fire(const char *zone, int64_t anchor, int64_t *next_out) {
    (void)zone;
    if (!next_out) {
        return -1;
    }
    load_policy();
    if (!g_repeat_guard) {
        *next_out = anchor + g_cadence;
        return 0;
    }
    if (g_prev_fire >= 0 && (anchor - g_prev_fire) == g_repeat_slot) {
        g_prev_fire = anchor;
        *next_out = anchor + g_cadence;
        return 2;
    }
    g_prev_fire = anchor;
    *next_out = anchor + g_cadence;
    return 0;
}
