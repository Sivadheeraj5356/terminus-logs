/*
 * lowess - locally weighted scatterplot smoothing (Cleveland 1979).
 *
 * Reads one JSON object from stdin:
 *   {"x":[...],"y":[...],"frac":<float>,"it":<int>,"delta":<float>}
 * and writes one line to stdout: a compact JSON array of the smoothed
 * y-values fitted at each input x, in input order.
 *
 * The governing standard is statsmodels.nonparametric.smoothers_lowess.lowess
 * (local degree-1 regression, tricube neighbor weights, bisquare robustifying
 * iterations, and delta linear-interpolation skipping).
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>

/* ------------------------------------------------------------------ */
/* Minimal JSON reading for the fixed input shape.                    */
/* ------------------------------------------------------------------ */

typedef struct {
    double *x;
    int nx;
    double *y;
    int ny;
    double frac;
    int it;
    double delta;
} Input;

static const char *skip_ws(const char *p) {
    while (*p == ' ' || *p == '\t' || *p == '\n' || *p == '\r')
        p++;
    return p;
}

/* Parse a JSON array of numbers starting at '['. Returns pointer past ']'. */
static const char *parse_num_array(const char *p, double **out, int *count) {
    int cap = 8, n = 0;
    double *buf = (double *)malloc(sizeof(double) * cap);
    p = skip_ws(p);
    if (*p != '[') { *out = buf; *count = 0; return p; }
    p++;
    p = skip_ws(p);
    if (*p == ']') { *out = buf; *count = 0; return p + 1; }
    while (1) {
        char *end;
        double v = strtod(p, &end);
        if (end == p) break;
        if (n == cap) { cap *= 2; buf = (double *)realloc(buf, sizeof(double) * cap); }
        buf[n++] = v;
        p = skip_ws(end);
        if (*p == ',') { p = skip_ws(p + 1); continue; }
        if (*p == ']') { p++; break; }
        break;
    }
    *out = buf;
    *count = n;
    return p;
}

/* Skip a JSON value we do not care about (object/array/string/literal). */
static const char *skip_value(const char *p) {
    p = skip_ws(p);
    if (*p == '"') {
        p++;
        while (*p && *p != '"') { if (*p == '\\' && p[1]) p++; p++; }
        if (*p == '"') p++;
        return p;
    }
    if (*p == '{' || *p == '[') {
        char open = *p, close = (open == '{') ? '}' : ']';
        int depth = 0;
        while (*p) {
            if (*p == '"') { p = skip_value(p); continue; }
            if (*p == open) depth++;
            else if (*p == close) { depth--; if (depth == 0) { p++; break; } }
            p++;
        }
        return p;
    }
    /* number / true / false / null */
    while (*p && *p != ',' && *p != '}' && *p != ']') p++;
    return p;
}

static int parse_input(const char *p, Input *in) {
    memset(in, 0, sizeof(*in));
    in->frac = 2.0 / 3.0;
    in->it = 3;
    in->delta = 0.0;
    p = skip_ws(p);
    if (*p != '{') return -1;
    p++;
    while (1) {
        p = skip_ws(p);
        if (*p == '}') { p++; break; }
        if (*p != '"') return -1;
        p++;
        const char *key = p;
        while (*p && *p != '"') p++;
        int klen = (int)(p - key);
        if (*p != '"') return -1;
        p++;
        p = skip_ws(p);
        if (*p != ':') return -1;
        p++;
        p = skip_ws(p);
        if (klen == 1 && key[0] == 'x') {
            p = parse_num_array(p, &in->x, &in->nx);
        } else if (klen == 1 && key[0] == 'y') {
            p = parse_num_array(p, &in->y, &in->ny);
        } else if (klen == 4 && strncmp(key, "frac", 4) == 0) {
            char *end; in->frac = strtod(p, &end); p = end;
        } else if (klen == 2 && strncmp(key, "it", 2) == 0) {
            char *end; in->it = (int)strtod(p, &end); p = end;
        } else if (klen == 5 && strncmp(key, "delta", 5) == 0) {
            char *end; in->delta = strtod(p, &end); p = end;
        } else {
            p = skip_value(p);
        }
        p = skip_ws(p);
        if (*p == ',') { p++; continue; }
        if (*p == '}') { p++; break; }
    }
    return 0;
}

/* ------------------------------------------------------------------ */
/* LOWESS core.                                                        */
/* ------------------------------------------------------------------ */

typedef struct { double x; int idx; } XI;

static int cmp_xi(const void *a, const void *b) {
    const XI *pa = (const XI *)a, *pb = (const XI *)b;
    if (pa->x < pb->x) return -1;
    if (pa->x > pb->x) return 1;
    /* stable on ties by original index */
    if (pa->idx < pb->idx) return -1;
    if (pa->idx > pb->idx) return 1;
    return 0;
}

static int cmp_double(const void *a, const void *b) {
    double da = *(const double *)a, db = *(const double *)b;
    if (da < db) return -1;
    if (da > db) return 1;
    return 0;
}

static double median_of(const double *v, int n) {
    double *tmp = (double *)malloc(sizeof(double) * n);
    memcpy(tmp, v, sizeof(double) * n);
    qsort(tmp, n, sizeof(double), cmp_double);
    double m;
    if (n % 2 == 1)
        m = tmp[n / 2];
    else
        m = (tmp[n / 2 - 1] + tmp[n / 2]) / 2.0;
    free(tmp);
    return m;
}

static void update_neighborhood(const double *x, double xval, int n,
                                int *left_end, int *right_end, double *radius) {
    int le = *left_end, re = *right_end;
    while (1) {
        if (re < n) {
            if (xval > ((x[le] + x[re]) / 2.0)) { le++; re++; }
            else break;
        } else break;
    }
    *left_end = le;
    *right_end = re;
    *radius = fmax(xval - x[le], x[re - 1] - xval);
}

static int calculate_weights(const double *x, double *weights, const double *rw,
                             double xval, int left_end, int right_end,
                             double radius) {
    int j;
    for (j = left_end; j < right_end; j++) {
        double d = fabs(x[j] - xval) / radius;
        double t = d * d * d;   /* tricube: (1 - d^3)^3 */
        t = 1.0 - t;
        t = t * t * t;
        weights[j] = t * rw[j];
    }
    double sum = 0.0;
    for (j = left_end; j < right_end; j++) sum += weights[j];
    int nonzero = 0;
    for (j = left_end; j < right_end; j++)
        if (weights[j] > 1e-12) nonzero++;
    if (nonzero < 2) return 0;
    for (j = left_end; j < right_end; j++) weights[j] /= sum;
    return 1;
}

static void calculate_y_fit(const double *x, const double *y, int i, double xval,
                            double *y_fit, const double *weights,
                            int left_end, int right_end, int reg_ok) {
    if (!reg_ok) {
        y_fit[i] = y[i];
        return;
    }
    int j;
    double sum_weighted_x = 0.0;
    for (j = left_end; j < right_end; j++)
        sum_weighted_x += weights[j] * x[j];
    double weighted_sqdev_x = 0.0;
    for (j = left_end; j < right_end; j++) {
        double dv = x[j] - sum_weighted_x;
        weighted_sqdev_x += weights[j] * dv * dv;
    }
    weighted_sqdev_x = fmax(weighted_sqdev_x, 1e-12);
    double acc = 0.0;
    for (j = left_end; j < right_end; j++) {
        double p = weights[j] * (1.0 + (xval - sum_weighted_x) *
                   (x[j] - sum_weighted_x) / weighted_sqdev_x);
        acc += p * y[j];
    }
    y_fit[i] = acc;
}

static void interpolate_skipped_fits(const double *xvals, double *y_fit,
                                     int i, int last_fit_i) {
    int offset = last_fit_i + 1;
    int nn = i - offset;
    double denom = xvals[i] - xvals[last_fit_i];
    int j;
    for (j = 0; j < nn; j++) {
        double a = (xvals[offset + j] - xvals[last_fit_i]) / denom;
        y_fit[offset + j] = a * y_fit[i] + (1.0 - a) * y_fit[last_fit_i];
    }
}

static void update_indices(const double *xvals, double *y_fit, double delta,
                           int *pi, int n, int *plast) {
    int last_fit_i = *pi;
    int kbreak = last_fit_i;
    double cutpoint = xvals[last_fit_i] + delta;
    int kk;
    for (kk = last_fit_i + 1; kk < n; kk++) {
        kbreak = kk;
        if (xvals[kk] > cutpoint) break;
        if (xvals[kk] == xvals[last_fit_i]) {
            y_fit[kk] = y_fit[last_fit_i];
            last_fit_i = kk;
        }
    }
    int i = kbreak - 1;
    if (last_fit_i + 1 > i) i = last_fit_i + 1;
    *pi = i;
    *plast = last_fit_i;
}

static void calculate_residual_weights(const double *y, const double *y_fit,
                                       int n, double *rw) {
    double *sr = (double *)malloc(sizeof(double) * n);
    int j;
    for (j = 0; j < n; j++) sr[j] = fabs(y[j] - y_fit[j]);
    double median = median_of(sr, n);
    if (median == 0.0) {
        for (j = 0; j < n; j++) sr[j] = (sr[j] > 0.0) ? 1.0 : 0.0;
    } else {
        double scale = 6.0 * median;
        for (j = 0; j < n; j++) sr[j] /= scale;
    }
    for (j = 0; j < n; j++) if (sr[j] > 1.0) sr[j] = 1.0;
    for (j = 0; j < n; j++) {
        double t = 1.0 - sr[j] * sr[j];
        rw[j] = t * t;
    }
    free(sr);
}

/*
 * Core smoother. x,y are given in INPUT order (length n); the fitted values
 * are written to out in INPUT order. Follows the statsmodels algorithm:
 * sort by x, run it+1 passes of local linear regression with tricube weights
 * and bisquare robustifying reweights, then scatter results back.
 */
void lowess_fit(const double *x_in, const double *y_in, int n,
                double frac, int it, double delta, double *out) {
    if (n <= 0) return;

    XI *order = (XI *)malloc(sizeof(XI) * n);
    int i, j;
    for (i = 0; i < n; i++) { order[i].x = x_in[i]; order[i].idx = i; }
    qsort(order, n, sizeof(XI), cmp_xi);

    double *x = (double *)malloc(sizeof(double) * n);
    double *y = (double *)malloc(sizeof(double) * n);
    for (i = 0; i < n; i++) {
        x[i] = x_in[order[i].idx];
        y[i] = y_in[order[i].idx];
    }

    int k = (int)(frac * n + 1e-10);
    if (k < 2) k = 2;
    if (k > n) k = n;

    double *rw = (double *)malloc(sizeof(double) * n);
    double *y_fit = (double *)malloc(sizeof(double) * n);
    double *weights = (double *)malloc(sizeof(double) * n);
    for (i = 0; i < n; i++) rw[i] = 1.0;

    int total = it + 1;
    int robiter;
    for (robiter = 0; robiter < total; robiter++) {
        int cur = 0;
        int last_fit_i = -1;
        int left_end = 0;
        int right_end = k;
        for (j = 0; j < n; j++) y_fit[j] = 0.0;

        while (1) {
            double xval = x[cur];
            for (j = 0; j < n; j++) weights[j] = 0.0;
            double radius;
            update_neighborhood(x, xval, n, &left_end, &right_end, &radius);
            int reg_ok = calculate_weights(x, weights, rw, xval,
                                           left_end, right_end, radius);
            calculate_y_fit(x, y, cur, xval, y_fit, weights,
                            left_end, right_end, reg_ok);
            if (last_fit_i < (cur - 1))
                interpolate_skipped_fits(x, y_fit, cur, last_fit_i);
            update_indices(x, y_fit, delta, &cur, n, &last_fit_i);
            if (last_fit_i >= n - 1) break;
        }

        calculate_residual_weights(y, y_fit, n, rw);
    }

    for (i = 0; i < n; i++)
        out[order[i].idx] = y_fit[i];

    free(order);
    free(x);
    free(y);
    free(rw);
    free(y_fit);
    free(weights);
}

/* ------------------------------------------------------------------ */
/* Entry point.                                                        */
/* ------------------------------------------------------------------ */

static char *read_all_stdin(void) {
    size_t cap = 4096, len = 0;
    char *buf = (char *)malloc(cap);
    size_t r;
    while ((r = fread(buf + len, 1, cap - len, stdin)) > 0) {
        len += r;
        if (len == cap) { cap *= 2; buf = (char *)realloc(buf, cap); }
    }
    buf[len] = '\0';
    return buf;
}

int main(void) {
    char *text = read_all_stdin();
    Input in;
    if (parse_input(text, &in) != 0) {
        fprintf(stderr, "invalid input\n");
        free(text);
        return 1;
    }
    int n = in.nx;
    if (in.ny < n) n = in.ny;

    double *out = (double *)malloc(sizeof(double) * (n > 0 ? n : 1));
    lowess_fit(in.x, in.y, n, in.frac, in.it, in.delta, out);

    putchar('[');
    int i;
    for (i = 0; i < n; i++) {
        if (i) putchar(',');
        printf("%.17g", out[i]);
    }
    putchar(']');
    putchar('\n');

    free(out);
    free(in.x);
    free(in.y);
    free(text);
    return 0;
}
