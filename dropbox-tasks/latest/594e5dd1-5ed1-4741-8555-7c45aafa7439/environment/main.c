/*
 * stringer (starter build). Sizes every zone in isolation. For each one it scores the zone's own
 * retired anodes for the share that reached end-of-life still live, converts that share into the
 * count that just meets the protection floor, and fills stock-route anodes ahead of expediter ones
 * until the shared allowance is gone. A placeholder only; the reference build takes its place before
 * any scoring. Run: ./bin/stringer data
 */
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define MAX_ZONES 512

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
    next_line(&cur);  /* header */
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
    /* buf is left allocated on purpose: the id strings sit inside it for as long as the run lasts */
    return n;
}

static void read_log(const char *path, Zone *zn, int n, long *trials, long *lasted) {
    for (int i = 0; i < n; i++) { trials[i] = 0; lasted[i] = 0; }
    char *buf = slurp(path);
    char *cur = buf;
    next_line(&cur);  /* header */
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

/* The least n at which the hold chance 1-(1-p)^n reaches the target. */
static long anodes_for(double p, double target) {
    p = clampd(p, 1e-6, 0.999999);
    return (long)ceil(log(1.0 - target) / log(1.0 - p));
}

/* Draw the shared stock down before any zone turns to an expediter. Zones are handled in order of how
 * far extra sits above stock on price, the widest saving first; each claims stock anodes until the
 * pool runs dry, and whatever it still owes past that point is charged at the extra rate. */
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
    free(pol_txt);

    /* Survival straight off the zone's own record: lasted over retired, lifted by a half count so a
     * near-empty record still gives a finite figure, then held inside the policy's permitted band. */
    long need[MAX_ZONES];
    for (int i = 0; i < n; i++) {
        double p = ((double)lasted[i] + 0.5) / ((double)trials[i] + 1.0);
        p = clampd(p, pol.surv_min, pol.surv_max);
        need[i] = anodes_for(p, pol.protection_floor);
    }

    Row rows[MAX_ZONES];
    allocate(zn, n, need, pol.stock_budget, rows);
    render(rows, n);
    return 0;
}
