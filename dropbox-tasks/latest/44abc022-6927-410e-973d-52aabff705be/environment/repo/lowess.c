/*
 * lowess - locally weighted scatterplot smoothing.
 *
 * Reads one JSON object from stdin:
 *   {"x":[...],"y":[...],"frac":<float>,"it":<int>,"delta":<float>}
 * and writes one line to stdout: a compact JSON array of the smoothed
 * y-values fitted at each input x, in input order.
 *
 * The standard-input decoding and standard-output formatting are already wired
 * up below. The numerical core, lowess_fit(), is not yet implemented: it
 * currently echoes the raw y-values, so the tool builds and runs but does not
 * actually smooth anything. Implement lowess_fit() so the fitted values match
 * the governing standard described in /app/SPEC.md.
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
/* Numerical core.                                                     */
/* ------------------------------------------------------------------ */

/*
 * Smooth (x, y) and write the fitted y-values to out, in input order.
 *
 * NOT YET IMPLEMENTED: this placeholder simply copies the raw y-values
 * through, so the tool runs but performs no smoothing. Replace the body with
 * a faithful implementation of the standard in /app/SPEC.md.
 */
void lowess_fit(const double *x, const double *y, int n,
                double frac, int it, double delta, double *out) {
    (void)x; (void)frac; (void)it; (void)delta;
    int i;
    for (i = 0; i < n; i++)
        out[i] = y[i];
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
