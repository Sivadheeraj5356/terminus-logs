/*
 * stringer (reference build). The starter trusts each zone's own retired anodes; this one goes the
 * other way. It regresses logged survival against resistivity across all forty zones by weighted least
 * squares, then assigns every zone a guarded rate a good way under that line. Where a zone has too few
 * retired anodes to speak for itself, the fitted figure carries it, and that reliance on the whole-run
 * fit is what stops the thinnest-logged zone from dragging the shared floor down. Counts land a touch
 * above the floor. Overwrites environment/main.c when the solution is applied.
 */
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define MAX_ZONES 512
#define Z_PRED 3.0
/* Size to a target set one step over the posted floor, leaving the least-sure zone room once real
 * survival arrives. FLOOR_HEADROOM sets how much of the distance from the floor up to a guaranteed
 * hold the target keeps in reserve; a 0.95 floor yields a 0.970 target. */
#define FLOOR_HEADROOM 0.6

typedef struct {
    char id[64];
    double resistivity;
    double stock_cost;
    double extra_cost;
} Zone;

typedef struct {
    double reference_resistivity;
    double surv_min;
    double surv_max;
    double protection_floor;
    long stock_budget;
    double cost_ceiling;
} Policy;

typedef struct {
    const char *id;
    long stock_anodes;
    long extra_anodes;
} Row;

static void die(const char *msg) {
    fprintf(stderr, "stringer: %s\n", msg);
    exit(1);
}

static char *slurp(const char *path) {
    FILE *f = fopen(path, "rb");
    if (!f) die(path);
    if (fseek(f, 0, SEEK_END) != 0) die("seek");
    long n = ftell(f);
    if (n < 0) die("tell");
    rewind(f);
    char *buf = malloc((size_t)n + 1);
    if (!buf) die("oom");
    size_t got = fread(buf, 1, (size_t)n, f);
    buf[got] = '\0';
    fclose(f);
    return buf;
}

/* Return one line (all of it before the next '\n') and advance *cur past that; NULL when spent. Edits in place. */
static char *next_line(char **cur) {
    char *s = *cur;
    if (!s || *s == '\0') return NULL;
    char *nl = strchr(s, '\n');
    if (nl) { *nl = '\0'; *cur = nl + 1; } else { *cur = s + strlen(s); }
    return s;
}

static double clampd(double x, double lo, double hi) {
    if (x < lo) return lo;
    if (x > hi) return hi;
    return x;
}

static double atof_trim(const char *s) {
    while (*s == ' ' || *s == '\t') s++;
    return atof(s);
}

/* Chop a writable line at every comma, noting up to maxf field heads; returns the count seen. */
static int split_fields(char *line, char **f, int maxf) {
    int n = 0;
    char *p = line;
    f[n++] = p;
    while (*p && n < maxf) {
        if (*p == ',') { *p = '\0'; f[n++] = p + 1; }
        p++;
    }
    for (int i = 0; i < n; i++) {
        char *e = f[i] + strlen(f[i]);
        while (e > f[i] && (e[-1] == '\r' || e[-1] == '\n')) *--e = '\0';
    }
    return n;
}

/* Grab the number after "<key>": locate the key text, step to its colon, convert the tail. A one-level file needs nothing more. */
static double json_number(const char *text, const char *key) {
    char needle[96];
    snprintf(needle, sizeof needle, "\"%s\"", key);
    const char *at = strstr(text, needle);
    if (!at) die(key);
    const char *colon = strchr(at + strlen(needle), ':');
    if (!colon) die(key);
    return atof_trim(colon + 1);
}

static int read_zones(const char *path, Zone *out) {
    char *buf = slurp(path);
    char *cur = buf;
    next_line(&cur);
    int n = 0;
    char *ln;
    while ((ln = next_line(&cur)) != NULL) {
        if (*ln == '\0') continue;
        char *f[8];
        if (split_fields(ln, f, 8) >= 4 && n < MAX_ZONES) {
            snprintf(out[n].id, sizeof out[n].id, "%s", f[0]);
            out[n].resistivity = atof_trim(f[1]);
            out[n].stock_cost = atof_trim(f[2]);
            out[n].extra_cost = atof_trim(f[3]);
            n++;
        }
    }
    return n;
}

static void read_log(const char *path, Zone *zn, int n, long *trials, long *lasted) {
    for (int i = 0; i < n; i++) { trials[i] = 0; lasted[i] = 0; }
    char *buf = slurp(path);
    char *cur = buf;
    next_line(&cur);
    char *ln;
    while ((ln = next_line(&cur)) != NULL) {
        if (*ln == '\0') continue;
        char *f[4];
        if (split_fields(ln, f, 4) >= 2) {
            for (int i = 0; i < n; i++) {
                if (strcmp(zn[i].id, f[0]) == 0) {
                    trials[i]++;
                    if (strcmp(f[1], "1") == 0) lasted[i]++;
                    break;
                }
            }
        }
    }
    free(buf);
}

static long anodes_for(double p, double target) {
    p = clampd(p, 1e-6, 0.999999);
    return (long)ceil(log(1.0 - target) / log(1.0 - p));
}

/* A zone's rate is drawn from the run as a whole, not its own anodes alone: weighted least squares of
 * log survival on (resistivity - reference), pulled Z_PRED prediction standard errors below the fit.
 * When a zone's record is too sparse to carry it, that lowered figure stands in for it, and this is
 * what stops a barely-logged zone from sinking the shared floor for everyone. */
static void estimate_rates(Zone *zn, int n, const long *trials, const long *lasted,
                           const Policy *pol, double *rates) {
    double *delta = malloc(sizeof(double) * n);
    double *y = malloc(sizeof(double) * n);
    double *w = malloc(sizeof(double) * n);
    double s1 = 0, sx = 0, sxx = 0, sy = 0, sxy = 0;
    for (int i = 0; i < n; i++) {
        double ph = ((double)lasted[i] + 0.5) / ((double)trials[i] + 1.0);
        delta[i] = zn[i].resistivity - pol->reference_resistivity;
        y[i] = log(ph);
        w[i] = (double)trials[i] * ph * (1.0 - ph);
        s1 += w[i];
        sx += w[i] * delta[i];
        sxx += w[i] * delta[i] * delta[i];
        sy += w[i] * y[i];
        sxy += w[i] * delta[i] * y[i];
    }
    double det = s1 * sxx - sx * sx;
    double b0 = (sxx * sy - sx * sxy) / det;
    double b1 = (s1 * sxy - sx * sy) / det;

    double wr2 = 0, wsum = 0;
    for (int i = 0; i < n; i++) {
        double r = y[i] - (b0 + b1 * delta[i]);
        wr2 += w[i] * r * r;
        wsum += w[i];
    }
    double s2 = wr2 / wsum * (double)n / ((double)n - 2.0);

    for (int i = 0; i < n; i++) {
        double v_mean = (sxx - 2.0 * delta[i] * sx + delta[i] * delta[i] * s1) / det;
        double sd = sqrt(fmax(v_mean + s2, 0.0));
        double theta = exp(b0 + b1 * delta[i] - Z_PRED * sd);
        rates[i] = clampd(theta, pol->surv_min, pol->surv_max);
    }
    free(delta);
    free(y);
    free(w);
}

static void allocate(Zone *zn, int n, const long *need, long stock_budget, Row *out) {
    int *order = malloc(sizeof(int) * n);
    for (int i = 0; i < n; i++) order[i] = i;
    for (int a = 0; a < n; a++)
        for (int b = a + 1; b < n; b++) {
            double sa = zn[order[a]].extra_cost - zn[order[a]].stock_cost;
            double sb = zn[order[b]].extra_cost - zn[order[b]].stock_cost;
            if (sb > sa) { int t = order[a]; order[a] = order[b]; order[b] = t; }
        }
    long *stock = calloc(n, sizeof(long));
    long remaining = stock_budget;
    for (int oi = 0; oi < n; oi++) {
        int i = order[oi];
        long take = need[i];
        if (take > remaining) take = remaining;
        if (take < 0) take = 0;
        stock[i] = take;
        remaining -= take;
    }
    for (int i = 0; i < n; i++) {
        out[i].id = zn[i].id;
        out[i].stock_anodes = stock[i];
        out[i].extra_anodes = need[i] - stock[i];
    }
    free(order);
    free(stock);
}

/* Emit no plan once a posted limit is crossed. At the rate each zone was sized on, its 1-(1-p)^n has
 * to sit at the floor or higher, and the stock-plus-extra spend summed over every zone has to stay
 * beneath the ceiling. If one of the two gives, the process quits without writing output. */
static void enforce_policy(const Row *rows, Zone *zn, int n, const double *rates,
                           const long *need, const Policy *pol) {
    for (int i = 0; i < n; i++) {
        double hold = 1.0 - pow(1.0 - rates[i], (double)need[i]);
        if (hold < pol->protection_floor) {
            char m[128];
            snprintf(m, sizeof m, "zone %s under protection floor: %.4f < %.4f",
                     zn[i].id, hold, pol->protection_floor);
            die(m);
        }
    }
    double cost = 0.0;
    for (int i = 0; i < n; i++) {
        cost += (double)rows[i].stock_anodes * zn[i].stock_cost;
        cost += (double)rows[i].extra_anodes * zn[i].extra_cost;
    }
    if (cost > pol->cost_ceiling) {
        char m[128];
        snprintf(m, sizeof m, "committed cost %.2f over ceiling %.2f", cost, pol->cost_ceiling);
        die(m);
    }
}

static void render(const Row *rows, int n) {
    printf("{\n  \"plan\": [\n");
    for (int i = 0; i < n; i++) {
        printf("    {\"zone_id\": \"%s\", \"stock_anodes\": %ld, \"extra_anodes\": %ld}",
               rows[i].id, rows[i].stock_anodes, rows[i].extra_anodes);
        printf(i + 1 < n ? ",\n" : "\n");
    }
    printf("  ]\n}\n");
}

int main(int argc, char **argv) {
    const char *dir = (argc > 1) ? argv[1] : "data";
    char path[1024];

    Zone zn[MAX_ZONES];
    snprintf(path, sizeof path, "%s/zones.csv", dir);
    int n = read_zones(path, zn);
    if (n == 0) die("no zones");

    long trials[MAX_ZONES], lasted[MAX_ZONES];
    snprintf(path, sizeof path, "%s/survival_log.csv", dir);
    read_log(path, zn, n, trials, lasted);

    snprintf(path, sizeof path, "%s/cp_policy.json", dir);
    char *pol_txt = slurp(path);
    Policy pol;
    pol.reference_resistivity = json_number(pol_txt, "reference_resistivity");
    pol.surv_min = json_number(pol_txt, "survival_min");
    pol.surv_max = json_number(pol_txt, "survival_max");
    pol.protection_floor = json_number(pol_txt, "protection_floor");
    pol.stock_budget = (long)json_number(pol_txt, "anode_stock_budget");
    pol.cost_ceiling = json_number(pol_txt, "cost_ceiling");
    free(pol_txt);

    double rates[MAX_ZONES];
    estimate_rates(zn, n, trials, lasted, &pol, rates);

    double target = 1.0 - (1.0 - pol.protection_floor) * FLOOR_HEADROOM;
    long need[MAX_ZONES];
    for (int i = 0; i < n; i++) need[i] = anodes_for(rates[i], target);

    Row rows[MAX_ZONES];
    allocate(zn, n, need, pol.stock_budget, rows);
    enforce_policy(rows, zn, n, rates, need, &pol);
    render(rows, n);
    return 0;
}
