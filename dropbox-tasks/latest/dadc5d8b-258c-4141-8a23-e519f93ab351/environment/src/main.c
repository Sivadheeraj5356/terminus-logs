#include "erfsum.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define FIELD_MAX 8192

static char *read_field(FILE *f) {
    char buf[FIELD_MAX];
    if (fscanf(f, "%8191s", buf) != 1) {
        return NULL;
    }
    size_t len = strlen(buf);
    char *s = malloc(len + 1);
    if (!s) {
        return NULL;
    }
    memcpy(s, buf, len + 1);
    return s;
}

int main(int argc, char **argv) {
    if (argc != 3) {
        fprintf(stderr, "usage: %s input.txt output.txt\n", argv[0]);
        return 2;
    }
    FILE *fin = fopen(argv[1], "r");
    if (!fin) {
        return 3;
    }
    int n = 0;
    if (fscanf(fin, "%d", &n) != 1 || n < 1) {
        fclose(fin);
        return 3;
    }
    char **c = malloc(sizeof(char *) * (size_t)n);
    char **x = malloc(sizeof(char *) * (size_t)n);
    for (int i = 0; i < n; i++) {
        c[i] = read_field(fin);
        x[i] = read_field(fin);
        if (!c[i] || !x[i]) {
            fclose(fin);
            return 3;
        }
    }
    fclose(fin);

    double out = 0.0;
    erfsum_weighted_sum(n, (const char *const *)c, (const char *const *)x, &out);

    FILE *fout = fopen(argv[2], "w");
    if (!fout) {
        return 3;
    }
    fprintf(fout, "%.17g\n", out);
    fclose(fout);

    for (int i = 0; i < n; i++) {
        free(c[i]);
        free(x[i]);
    }
    free(c);
    free(x);
    return 0;
}
