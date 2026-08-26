#define _POSIX_C_SOURCE 200809L
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <dirent.h>

#define TSTAR 5.0
#define MAXROW 256
#define DT 0.002

typedef struct {
    double ts[MAXROW], A[MAXROW], B[MAXROW], P[MAXROW], D[MAXROW];
    int n;
} Data;

static int cmpstr(const void *a, const void *b) {
    return strcmp(*(const char *const *)a, *(const char *const *)b);
}

/* Reversible coupled two-state model on-surface fractions.
   State vector x=[A;B], x(0)=[1;0],
       dA/dt = -a A + kBA B,   dB/dt = kAB A - b B,
   where a,b are the TOTAL exit rates of A,B (conversion + decomposition +
   activation/back-reaction + desorption). */
typedef struct { double lp, lm, Cp0, Cm0, Cp1, Cm1; } Modes;

static Modes modes(double a, double b, double kAB, double kBA) {
    Modes m;
    double tr = -(a + b);
    double det = a * b - kAB * kBA;
    double disc = sqrt(tr * tr - 4.0 * det);
    if (disc < 1e-12) disc = 1e-12;
    m.lp = (tr + disc) / 2.0;
    m.lm = (tr - disc) / 2.0;
    double denom = m.lp - m.lm;
    m.Cp0 = (-a - m.lm) / denom;  m.Cp1 = kAB / denom;
    m.Cm0 = (a + m.lp) / denom;   m.Cm1 = -kAB / denom;
    return m;
}

static double emode(double lam, double t) {
    return (fabs(lam) > 1e-12) ? (exp(lam * t) - 1.0) / lam : t;
}

static void curve(const Modes *m, double t, double *A, double *B,
                  double *IA, double *IB) {
    double ep = exp(m->lp * t), em = exp(m->lm * t);
    *A = m->Cp0 * ep + m->Cm0 * em;
    *B = m->Cp1 * ep + m->Cm1 * em;
    *IA = m->Cp0 * emode(m->lp, t) + m->Cm0 * emode(m->lm, t);
    *IB = m->Cp1 * emode(m->lp, t) + m->Cm1 * emode(m->lm, t);
}

static void linfit2(const double *x1, const double *x2, const double *y, int n,
                    double *c1, double *c2) {
    double s11 = 0, s22 = 0, s12 = 0, sy1 = 0, sy2 = 0;
    for (int i = 0; i < n; i++) {
        s11 += x1[i] * x1[i]; s22 += x2[i] * x2[i]; s12 += x1[i] * x2[i];
        sy1 += x1[i] * y[i]; sy2 += x2[i] * y[i];
    }
    double det = s11 * s22 - s12 * s12;
    if (fabs(det) < 1e-15) { *c1 = 0; *c2 = 0; return; }
    *c1 = (sy1 * s22 - sy2 * s12) / det;
    *c2 = (s11 * sy2 - s12 * sy1) / det;
}

static double sse_AB(const Data *d, double a, double b, double kAB, double kBA) {
    Modes m = modes(a, b, kAB, kBA);
    double s = 0;
    for (int i = 0; i < d->n; i++) {
        double A, B, IA, IB;
        curve(&m, d->ts[i], &A, &B, &IA, &IB);
        double eA = A - d->A[i], eB = B - d->B[i];
        s += eA * eA + eB * eB;
    }
    return s;
}

/* On-surface product is a filtered source: dP/dt = kAP A + kBP B - kPdes P.
   For fixed kPdes, P(t) = kAP φA(t) + kBP φB(t) with
   φX(t) = ∫_0^t exp(-kPdes (t-s)) X(s) ds. */
static void filtered_basis(const Modes *m, double kPdes, double tmax,
                           const double *ts, int n,
                           double *fA, double *fB) {
    int ngrid = (int)floor(tmax / DT + 0.5) + 1;
    if (ngrid < 2) ngrid = 2;
    double *Aa = malloc((size_t)ngrid * sizeof(double));
    double *Bb = malloc((size_t)ngrid * sizeof(double));
    double *Fa = calloc((size_t)ngrid, sizeof(double));
    double *Fb = calloc((size_t)ngrid, sizeof(double));
    if (!Aa || !Bb || !Fa || !Fb) { fprintf(stderr, "oom\n"); exit(1); }
    for (int i = 0; i < ngrid; i++) {
        double t = i * DT, IA, IB;
        curve(m, t, &Aa[i], &Bb[i], &IA, &IB);
    }
    double e = exp(-kPdes * DT);
    double gain = (kPdes > 1e-12) ? (1.0 - e) / kPdes : DT;
    for (int i = 1; i < ngrid; i++) {
        double sA = 0.5 * (Aa[i - 1] + Aa[i]);
        double sB = 0.5 * (Bb[i - 1] + Bb[i]);
        Fa[i] = Fa[i - 1] * e + sA * gain;
        Fb[i] = Fb[i - 1] * e + sB * gain;
    }
    for (int j = 0; j < n; j++) {
        int idx = (int)floor(ts[j] / DT + 0.5);
        if (idx < 0) idx = 0;
        if (idx >= ngrid) idx = ngrid - 1;
        fA[j] = Fa[idx];
        fB[j] = Fb[idx];
    }
    free(Aa); free(Bb); free(Fa); free(Fb);
}

static double sse_P(const Data *d, const Modes *m, double kPdes,
                    double *kAP, double *kBP) {
    double fA[MAXROW], fB[MAXROW];
    double tmax = d->ts[d->n - 1];
    filtered_basis(m, kPdes, tmax, d->ts, d->n, fA, fB);
    linfit2(fA, fB, d->P, d->n, kAP, kBP);
    double s = 0;
    for (int i = 0; i < d->n; i++) {
        double e = (*kAP) * fA[i] + (*kBP) * fB[i] - d->P[i];
        s += e * e;
    }
    return s;
}

static void fit(const Data *d, double *pa, double *pb, double *pkAB, double *pkBA,
                double *kAP, double *kBP, double *kPdes,
                double *kAD, double *kBD) {
    double best = 1e300, ba = 0.8, bb = 1.0, bAB = 0.3, bBA = 0.5;
    for (double a = 0.3; a <= 3.2; a += 0.19)
        for (double b = 0.4; b <= 4.2; b += 0.22)
            for (double kAB = 0.05; kAB <= 1.45; kAB += 0.15)
                for (double kBA = 0.05; kBA <= 1.55; kBA += 0.15) {
                    double r = sse_AB(d, a, b, kAB, kBA);
                    if (r < best) { best = r; ba = a; bb = b; bAB = kAB; bBA = kBA; }
                }
    double step[4] = {0.19, 0.22, 0.15, 0.15};
    double x[4] = {ba, bb, bAB, bBA};
    for (int it = 0; it < 500; it++) {
        int improved = 0;
        for (int k = 0; k < 4; k++) {
            for (int s = -1; s <= 1; s += 2) {
                double trial[4] = {x[0], x[1], x[2], x[3]};
                trial[k] += s * step[k];
                if (trial[0] <= 0 || trial[1] <= 0 || trial[2] < 0 || trial[3] < 0)
                    continue;
                double r = sse_AB(d, trial[0], trial[1], trial[2], trial[3]);
                if (r < best) { best = r; memcpy(x, trial, sizeof(x)); improved = 1; }
            }
        }
        if (!improved) { for (int k = 0; k < 4; k++) step[k] *= 0.5; }
        if (step[0] < 1e-7 && step[1] < 1e-7 && step[2] < 1e-7 && step[3] < 1e-7) break;
    }
    *pa = x[0]; *pb = x[1]; *pkAB = x[2]; *pkBA = x[3];
    Modes m = modes(x[0], x[1], x[2], x[3]);

    /* Scan product-desorption rate; for each, LS the conversion rates on the
       exponentially filtered A,B bases. */
    double bestP = 1e300, bkP = 0.3, bkAP = 0.1, bkBP = 0.5;
    for (double kp = 0.05; kp <= 0.90; kp += 0.025) {
        double c1, c2;
        double r = sse_P(d, &m, kp, &c1, &c2);
        if (r < bestP) { bestP = r; bkP = kp; bkAP = c1; bkBP = c2; }
    }
    double kp_step = 0.025;
    for (int it = 0; it < 80; it++) {
        int improved = 0;
        for (int s = -1; s <= 1; s += 2) {
            double trial = bkP + s * kp_step;
            if (trial < 0.01 || trial > 1.5) continue;
            double c1, c2;
            double r = sse_P(d, &m, trial, &c1, &c2);
            if (r < bestP) { bestP = r; bkP = trial; bkAP = c1; bkBP = c2; improved = 1; }
        }
        if (!improved) kp_step *= 0.5;
        if (kp_step < 1e-5) break;
    }
    *kAP = bkAP; *kBP = bkBP; *kPdes = bkP;

    double IAv[MAXROW], IBv[MAXROW];
    for (int i = 0; i < d->n; i++) {
        double A, B, IA, IB;
        curve(&m, d->ts[i], &A, &B, &IA, &IB);
        IAv[i] = IA; IBv[i] = IB;
    }
    linfit2(IAv, IBv, d->D, d->n, kAD, kBD);
}

/* Loss-free cumulative conversion at t=TSTAR: drop reactant desorption,
   re-solve the coupled system, integrate product formation. Product
   desorption does not change how many molecules converted. */
static double lossfree_conv(double kAB, double kBA, double kAP, double kBP,
                            double kAD, double kBD) {
    double a = kAP + kAD + kAB;
    double b = kBP + kBD + kBA;
    Modes m = modes(a, b, kAB, kBA);
    double A, B, IA, IB;
    curve(&m, TSTAR, &A, &B, &IA, &IB);
    return kAP * IA + kBP * IB;
}

static void read_counts(const char *path, Data *d) {
    FILE *f = fopen(path, "r");
    if (!f) { fprintf(stderr, "cannot open %s\n", path); exit(1); }
    char line[512];
    int first = 1;
    double N0 = 1.0;
    d->n = 0;
    while (fgets(line, sizeof(line), f)) {
        if (first) { first = 0; continue; }
        char *nl = strpbrk(line, "\r\n");
        if (nl) *nl = '\0';
        if (line[0] == '\0') continue;
        char *save = NULL;
        char *st = strtok_r(line, ",", &save);
        char *sa = strtok_r(NULL, ",", &save);
        char *sb = strtok_r(NULL, ",", &save);
        char *sp = strtok_r(NULL, ",", &save);
        char *sd = strtok_r(NULL, ",", &save);
        if (!st || !sa || !sb || !sp || !sd) continue;
        int i = d->n;
        if (i == 0) N0 = atof(sa);
        d->ts[i] = atof(st);
        d->A[i] = atof(sa);
        d->B[i] = atof(sb);
        d->P[i] = atof(sp);
        d->D[i] = atof(sd);
        d->n++;
        if (d->n >= MAXROW) break;
    }
    fclose(f);
    if (N0 <= 0) N0 = 1.0;
    for (int i = 0; i < d->n; i++) {
        d->A[i] /= N0; d->B[i] /= N0; d->P[i] /= N0; d->D[i] /= N0;
    }
}

int main(int argc, char **argv) {
    const char *dir = argc > 1 ? argv[1] : "/app/reactor";
    DIR *dp = opendir(dir);
    if (!dp) { fprintf(stderr, "cannot open %s\n", dir); return 1; }
    char **names = malloc(16 * sizeof(char *));
    size_t cap = 16, nn = 0;
    struct dirent *e;
    while ((e = readdir(dp))) {
        if (e->d_name[0] == '.') continue;
        char probe[1024];
        snprintf(probe, sizeof(probe), "%s/%s/counts.csv", dir, e->d_name);
        FILE *t = fopen(probe, "r");
        if (!t) continue;
        fclose(t);
        if (nn == cap) { cap *= 2; names = realloc(names, cap * sizeof(char *)); }
        names[nn++] = strdup(e->d_name);
    }
    closedir(dp);
    qsort(names, nn, sizeof(char *), cmpstr);

    for (size_t k = 0; k < nn; k++) {
        char spath[1024], opath[1024];
        snprintf(spath, sizeof(spath), "%s/%s/counts.csv", dir, names[k]);
        snprintf(opath, sizeof(opath), "%s/%s/conversion.txt", dir, names[k]);
        Data d;
        read_counts(spath, &d);
        double a, b, kAB, kBA, kAP, kBP, kPdes, kAD, kBD;
        fit(&d, &a, &b, &kAB, &kBA, &kAP, &kBP, &kPdes, &kAD, &kBD);
        double y = lossfree_conv(kAB, kBA, kAP, kBP, kAD, kBD);
        FILE *o = fopen(opath, "w");
        if (!o) { fprintf(stderr, "cannot write %s\n", opath); return 1; }
        fprintf(o, "%.4f\n", y);
        fclose(o);
        printf("%s %.4f\n", names[k], y);
        free(names[k]);
    }
    free(names);
    return 0;
}
