#include "commit_log.h"

#include <stdio.h>
#include <string.h>

int commit_log_append(const char *path, const char *window, const char *key, int seq, int flags) {
    if (!path || !window || !key) {
        return -1;
    }
    FILE *fp = fopen(path, "a");
    if (!fp) {
        return -2;
    }
    fprintf(fp, "%s\t%s\t%d\t%d\n", window, key, seq, flags);
    fclose(fp);
    return 0;
}

int commit_log_has_key(const char *path, const char *key) {
    if (!path || !key || !key[0]) {
        return 0;
    }
    FILE *fp = fopen(path, "r");
    if (!fp) {
        return 0;
    }
    char line[256];
    while (fgets(line, sizeof line, fp)) {
        char win[16];
        char k[32];
        int seq = 0;
        int fl = 0;
        if (sscanf(line, "%15s %31s %d %d", win, k, &seq, &fl) >= 2) {
            if (strcmp(k, key) == 0) {
                fclose(fp);
                return 1;
            }
        }
    }
    fclose(fp);
    return 0;
}

int commit_log_finest_for_day(const char *path, const char *day8, char *out, size_t cap) {
    if (!path || !day8 || !out || cap == 0) {
        return -1;
    }
    out[0] = '\0';
    FILE *fp = fopen(path, "r");
    if (!fp) {
        return -2;
    }
    char best[32] = "";
    char line[256];
    while (fgets(line, sizeof line, fp)) {
        char win[16];
        char k[32];
        int seq = 0;
        int fl = 0;
        if (sscanf(line, "%15s %31s %d %d", win, k, &seq, &fl) < 2) {
            continue;
        }
        if (strncmp(k, day8, 8) != 0) {
            continue;
        }
        if (!best[0] || strlen(k) > strlen(best) || (strlen(k) == strlen(best) && strcmp(k, best) < 0)) {
            strncpy(best, k, sizeof best - 1);
            best[sizeof best - 1] = '\0';
        }
    }
    fclose(fp);
    if (!best[0]) {
        return -3;
    }
    strncpy(out, best, cap - 1);
    out[cap - 1] = '\0';
    return 0;
}
