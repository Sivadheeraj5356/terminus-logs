/* Shared harness for the damped-wave wrong-baseline schemes.
 *
 * These baselines are external test instruments, not the graded task. Each one
 * supplies a `bl_step` update and calls `bl_run_main`; the harness handles JSON
 * input, initial-profile sampling, and the CSV output (columns t,x,u,v, matching
 * the environment driver). The state array has length 2N: displacement in
 * state[0..N-1] and velocity in state[N..2N-1]. None of this is visible to the
 * agent. */
#ifndef BASELINE_HARNESS_H
#define BASELINE_HARNESS_H

#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

#define BL_MAXTERM 64
#define BL_MAXSNAP 64

typedef struct {
    int is_gauss;
    double center, width, c0;
    int nterm;
    double amps[BL_MAXTERM], waves[BL_MAXTERM], phases[BL_MAXTERM];
} BlProfile;

typedef struct {
    double c;
    double g;
    int N;
    double nu;
    double T;
    int nsnap;
    double snaps[BL_MAXSNAP];
    BlProfile prof;
} BlRun;

static const char *bl_vstart(const char *s, const char *key) {
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
static double bl_scalar(const char *s, const char *key) {
    return strtod(bl_vstart(s, key), NULL);
}
static int bl_int(const char *s, const char *key) {
    return (int)floor(bl_scalar(s, key) + 0.5);
}
static int bl_array(const char *s, const char *key, double *buf, int maxn) {
    const char *p = bl_vstart(s, key);
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
        if (end == q) break;
        buf[n++] = v;
        q = end;
        while (q < rb && (*q == ',' || *q == ' ' || *q == '\n' || *q == '\t')) q++;
    }
    return n;
}
static void bl_string(const char *s, const char *key, char *buf, int maxn) {
    const char *p = bl_vstart(s, key);
    while (*p && *p != '"') p++;
    p++;
    int n = 0;
    while (*p && *p != '"' && n < maxn - 1) buf[n++] = *p++;
    buf[n] = '\0';
}

static void bl_read(const char *path, BlRun *r) {
    FILE *f = fopen(path, "rb");
    if (!f) { fprintf(stderr, "cannot open input\n"); exit(1); }
    fseek(f, 0, SEEK_END);
    long sz = ftell(f);
    fseek(f, 0, SEEK_SET);
    char *s = (char *)malloc(sz + 1);
    if (fread(s, 1, sz, f) != (size_t)sz) { fprintf(stderr, "short read\n"); exit(1); }
    s[sz] = '\0';
    fclose(f);
    r->c = bl_scalar(s, "c");
    r->g = bl_scalar(s, "g");
    r->N = bl_int(s, "N");
    r->nu = bl_scalar(s, "nu");
    r->T = bl_scalar(s, "T");
    r->nsnap = bl_array(s, "snapshots", r->snaps, BL_MAXSNAP);
    BlProfile *p = &r->prof;
    memset(p, 0, sizeof(*p));
    char kind[32];
    bl_string(s, "kind", kind, sizeof(kind));
    if (strcmp(kind, "gaussian") == 0) {
        p->is_gauss = 1;
        p->center = bl_scalar(s, "center");
        p->width = bl_scalar(s, "width");
    } else {
        p->is_gauss = 0;
        p->c0 = bl_scalar(s, "const");
        p->nterm = bl_array(s, "amps", p->amps, BL_MAXTERM);
        bl_array(s, "waves", p->waves, BL_MAXTERM);
        bl_array(s, "phases", p->phases, BL_MAXTERM);
    }
    free(s);
}

static double bl_prof_eval(const BlProfile *p, double x) {
    if (p->is_gauss) {
        double d = x - p->center;
        d = d - round(d);
        return exp(-(d / p->width) * (d / p->width));
    }
    double v = p->c0;
    for (int j = 0; j < p->nterm; j++)
        v += p->amps[j] * sin(2.0 * M_PI * p->waves[j] * x + p->phases[j]);
    return v;
}

/* Fourth-order 5-point periodic second-derivative stencil (shared by the
 * baselines that keep the correct spatial operator). */
static void bl_d2_4(const double *u, double *out, int N, double inv12dx2) {
    for (int i = 0; i < N; i++) {
        int im2 = (i - 2 + N) % N, im1 = (i - 1 + N) % N;
        int ip1 = (i + 1) % N, ip2 = (i + 2) % N;
        out[i] = (-u[im2] + 16.0 * u[im1] - 30.0 * u[i] + 16.0 * u[ip1] - u[ip2]) *
                 inv12dx2;
    }
}

/* Sixth-order 7-point periodic second-derivative stencil (shared by the
 * baselines that keep the sixth-order spatial operator; inv_dx2 = 1/dx^2). */
static void bl_d2_6(const double *u, double *out, int N, double inv_dx2) {
    for (int i = 0; i < N; i++) {
        int m3 = (i - 3 + N) % N, m2 = (i - 2 + N) % N, m1 = (i - 1 + N) % N;
        int p1 = (i + 1) % N, p2 = (i + 2) % N, p3 = (i + 3) % N;
        out[i] = ((1.0 / 90.0) * u[m3] - (3.0 / 20.0) * u[m2] +
                  (3.0 / 2.0) * u[m1] - (49.0 / 18.0) * u[i] +
                  (3.0 / 2.0) * u[p1] - (3.0 / 20.0) * u[p2] +
                  (1.0 / 90.0) * u[p3]) *
                 inv_dx2;
    }
}

/* Driver: sample the initial displacement, start from rest, then for each
 * snapshot call step() to carry the state from the previous time to the snapshot
 * time, and write columns t,x,u,v. */
static int bl_run_main(int argc, char **argv,
                       void (*step)(const BlRun *, double *, double, double)) {
    if (argc < 3) { fprintf(stderr, "usage: solver <in> <out>\n"); return 1; }
    BlRun r;
    bl_read(argv[1], &r);
    int N = r.N;
    double dx = 1.0 / (double)N;
    double *state = (double *)calloc((size_t)2 * N, sizeof(double));
    for (int i = 0; i < N; i++) state[i] = bl_prof_eval(&r.prof, i * dx);
    FILE *o = fopen(argv[2], "wb");
    if (!o) { fprintf(stderr, "cannot open output\n"); return 1; }
    fprintf(o, "t,x,u,v\n");
    double t = 0.0;
    for (int k = 0; k < r.nsnap; k++) {
        double ts = r.snaps[k];
        step(&r, state, t, ts);
        t = ts;
        for (int i = 0; i < N; i++)
            fprintf(o, "%.16e,%.16e,%.16e,%.16e\n", ts, i * dx, state[i],
                    state[(size_t)N + i]);
    }
    fclose(o);
    free(state);
    return 0;
}

#endif /* BASELINE_HARNESS_H */
