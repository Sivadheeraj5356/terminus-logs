#include "theta.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* Read one whitespace-separated token into a freshly allocated string. */
static char *read_token(FILE *f) {
    char buf[4096];
    if (fscanf(f, "%4095s", buf) != 1) return NULL;
    size_t n = strlen(buf);
    char *s = malloc(n + 1);
    if (!s) return NULL;
    memcpy(s, buf, n + 1);
    return s;
}

int main(int argc, char **argv) {
    if (argc != 3) {
        fprintf(stderr, "usage: %s input.txt output.txt\n", argv[0]);
        return 2;
    }

    FILE *fin = fopen(argv[1], "r");
    if (!fin) {
        fprintf(stderr, "cannot open input file %s\n", argv[1]);
        return 3;
    }
    int n = 0;
    if (fscanf(fin, "%d", &n) != 1 || n < 1) {
        fprintf(stderr, "bad term count\n");
        fclose(fin);
        return 3;
    }
    char **c = malloc(sizeof(char *) * (size_t)n);
    char **z = malloc(sizeof(char *) * (size_t)n);
    char **q = malloc(sizeof(char *) * (size_t)n);
    if (!c || !z || !q) {
        fclose(fin);
        return 4;
    }
    for (int i = 0; i < n; i++) {
        c[i] = read_token(fin);
        z[i] = read_token(fin);
        q[i] = read_token(fin);
        if (!c[i] || !z[i] || !q[i]) {
            fprintf(stderr, "missing term %d\n", i);
            fclose(fin);
            return 3;
        }
    }
    fclose(fin);

    double out = 0.0;
    theta3(n, (const char *const *)c, (const char *const *)z,
           (const char *const *)q, &out);

    FILE *fout = fopen(argv[2], "w");
    if (!fout) {
        fprintf(stderr, "cannot open output file %s\n", argv[2]);
        return 3;
    }
    fprintf(fout, "%.17g\n", out);
    fclose(fout);

    for (int i = 0; i < n; i++) {
        free(c[i]);
        free(z[i]);
        free(q[i]);
    }
    free(c);
    free(z);
    free(q);
    return 0;
}
