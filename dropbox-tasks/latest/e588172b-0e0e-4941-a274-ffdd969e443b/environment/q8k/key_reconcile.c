#include <stdio.h>
#include <string.h>

static void pick_canon(const char *a, const char *b, char *out, size_t cap) {
    if (!a[0]) {
        strncpy(out, b, cap - 1);
        out[cap - 1] = '\0';
        return;
    }
    if (!b[0]) {
        strncpy(out, a, cap - 1);
        out[cap - 1] = '\0';
        return;
    }
    size_t la = strlen(a);
    size_t lb = strlen(b);
    size_t pa = la >= 8 ? 8 : la;
    size_t pb = lb >= 8 ? 8 : lb;
    if (pa == pb && strncmp(a, b, pa) == 0) {
        strncpy(out, (la <= lb) ? a : b, cap - 1);
    } else if (strcmp(a, b) < 0) {
        strncpy(out, a, cap - 1);
    } else {
        strncpy(out, b, cap - 1);
    }
    out[cap - 1] = '\0';
}

int reconcile_key(const char *rows_path, char *key_out, size_t cap) {
    if (!rows_path || !key_out || cap == 0) {
        return -1;
    }
    FILE *fp = fopen(rows_path, "r");
    if (!fp) {
        return -2;
    }
    char line[256];
    char canon[32] = "";
    while (fgets(line, sizeof line, fp)) {
        if (line[0] == '#' || line[0] == '\n') {
            continue;
        }
        char key[32];
        if (sscanf(line, "%31[^|]", key) != 1) {
            continue;
        }
        char next[32];
        pick_canon(canon, key, next, sizeof next);
        strncpy(canon, next, sizeof canon - 1);
        canon[sizeof canon - 1] = '\0';
    }
    fclose(fp);
    if (!canon[0]) {
        return -3;
    }
    strncpy(key_out, canon, cap - 1);
    key_out[cap - 1] = '\0';
    return 0;
}
