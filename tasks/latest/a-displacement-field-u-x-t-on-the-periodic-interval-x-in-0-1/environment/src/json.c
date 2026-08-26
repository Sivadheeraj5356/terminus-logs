#include "json.h"

#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* Locate "key" in the buffer and return the position just past the following
 * colon. A missing key or absent colon is a fatal input error. */
static const char *value_start(const char *s, const char *key) {
    char pat[64];
    snprintf(pat, sizeof(pat), "\"%s\"", key);
    const char *k = strstr(s, pat);
    if (!k) {
        fprintf(stderr, "input key missing: %s\n", key);
        exit(1);
    }
    const char *c = strchr(k + strlen(pat), ':');
    if (!c) {
        fprintf(stderr, "malformed input near %s\n", key);
        exit(1);
    }
    return c + 1;
}

char *json_read_file(const char *path, long *out_size) {
    FILE *f = fopen(path, "rb");
    if (!f) {
        return NULL;
    }
    fseek(f, 0, SEEK_END);
    long sz = ftell(f);
    fseek(f, 0, SEEK_SET);
    char *s = (char *)malloc(sz + 1);
    if (!s) {
        fclose(f);
        return NULL;
    }
    if (fread(s, 1, sz, f) != (size_t)sz) {
        free(s);
        fclose(f);
        return NULL;
    }
    s[sz] = '\0';
    fclose(f);
    if (out_size) {
        *out_size = sz;
    }
    return s;
}

double json_scalar(const char *s, const char *key) {
    return strtod(value_start(s, key), NULL);
}

int json_int(const char *s, const char *key) {
    return (int)floor(json_scalar(s, key) + 0.5);
}

int json_array(const char *s, const char *key, double *buf, int maxn) {
    const char *p = value_start(s, key);
    const char *lb = strchr(p, '[');
    const char *rb = strchr(p, ']');
    if (!lb || !rb || rb < lb) {
        fprintf(stderr, "malformed array %s\n", key);
        exit(1);
    }
    int n = 0;
    const char *q = lb + 1;
    while (q < rb && n < maxn) {
        char *end;
        double v = strtod(q, &end);
        if (end == q) {
            break;
        }
        buf[n++] = v;
        q = end;
        while (q < rb && (*q == ',' || *q == ' ' || *q == '\n' || *q == '\t')) {
            q++;
        }
    }
    return n;
}

void json_string(const char *s, const char *key, char *buf, int maxn) {
    const char *p = value_start(s, key);
    while (*p && *p != '"') {
        p++;
    }
    if (*p != '"') {
        fprintf(stderr, "malformed string %s\n", key);
        exit(1);
    }
    p++;
    int n = 0;
    while (*p && *p != '"' && n < maxn - 1) {
        buf[n++] = *p++;
    }
    buf[n] = '\0';
}
