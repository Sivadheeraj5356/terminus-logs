#include "tel_config.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define TEL_MAX_SCENARIOS 16
#define TEL_SCENARIO_ID_LEN 64

typedef struct {
    char id[TEL_SCENARIO_ID_LEN];
    uint64_t window_ns;
} tel_scenario_window_t;

static uint64_t g_default_window = 60000000000ULL;
static tel_scenario_window_t g_scenarios[TEL_MAX_SCENARIOS];
static size_t g_scenario_count = 0;

static char *trim(char *s) {
    while (*s == ' ' || *s == '\t') {
        s++;
    }
    char *end = s + strlen(s);
    while (end > s && (end[-1] == ' ' || end[-1] == '\t' || end[-1] == '\n' || end[-1] == '\r')) {
        *--end = '\0';
    }
    return s;
}

static int parse_u64(const char *s, uint64_t *out) {
    char *end = NULL;
    unsigned long long v = strtoull(s, &end, 10);
    if (end == s) {
        return -1;
    }
    *out = (uint64_t)v;
    return 0;
}

static void store_scenario_window(const char *section, uint64_t window) {
    const char *prefix = "scenarios.";
    size_t plen = strlen(prefix);
    if (strncmp(section, prefix, plen) != 0) {
        return;
    }
    if (g_scenario_count >= TEL_MAX_SCENARIOS) {
        return;
    }
    tel_scenario_window_t *row = &g_scenarios[g_scenario_count++];
    strncpy(row->id, section + plen, sizeof(row->id) - 1);
    row->window_ns = window;
}

int tel_config_init(const char *path) {
    FILE *fp = fopen(path, "r");
    if (!fp) {
        return -1;
    }

    char line[512];
    char current_section[128] = "";
    while (fgets(line, sizeof(line), fp)) {
        char *p = trim(line);
        if (*p == '#' || *p == '\0') {
            continue;
        }
        if (*p == '[') {
            char *end = strchr(p, ']');
            if (!end) {
                continue;
            }
            *end = '\0';
            strncpy(current_section, p + 1, sizeof(current_section) - 1);
            continue;
        }
        char *eq = strchr(p, '=');
        if (!eq) {
            continue;
        }
        *eq = '\0';
        char *key = trim(p);
        char *val = trim(eq + 1);
        uint64_t window = 0;
        if (strcmp(key, "correlation_window_ns_default") == 0 && parse_u64(val, &window) == 0) {
            g_default_window = window;
        } else if (strcmp(key, "correlation_window_ns") == 0 && parse_u64(val, &window) == 0) {
            if (current_section[0]) {
                store_scenario_window(current_section, window);
            }
        }
    }
    fclose(fp);
    return 0;
}

uint64_t tel_config_window_ns(const char *scenario_id) {
    (void)scenario_id;
    if (g_scenario_count > 0) {
        return g_scenarios[0].window_ns;
    }
    return g_default_window;
}

int tel_config_validate_loaded(void) {
    return g_default_window > 0 ? 0 : -1;
}

void tel_config_shutdown(void) {
    g_scenario_count = 0;
    g_default_window = 60000000000ULL;
}
