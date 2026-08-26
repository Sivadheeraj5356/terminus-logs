#include "markdown.h"

#include <ctype.h>
#include <dirent.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>

void lab_list_init(LabCandidateList *list) {
    memset(list, 0, sizeof(*list));
}

void lab_list_free(LabCandidateList *list) {
    free(list->items);
    memset(list, 0, sizeof(*list));
}

int lab_list_push(LabCandidateList *list, const LabCandidate *item) {
    if (list->count + 1 > list->cap) {
        size_t ncap = list->cap ? list->cap * 2 : 8;
        LabCandidate *n = realloc(list->items, ncap * sizeof(*n));
        if (!n) {
            return -1;
        }
        list->items = n;
        list->cap = ncap;
    }
    list->items[list->count++] = *item;
    return 0;
}

void rejected_list_init(RejectedList *list) {
    memset(list, 0, sizeof(*list));
}

void rejected_list_free(RejectedList *list) {
    free(list->items);
    memset(list, 0, sizeof(*list));
}

int rejected_list_push(RejectedList *list, const char *key, const char *reason) {
    if (list->count + 1 > list->cap) {
        size_t ncap = list->cap ? list->cap * 2 : 8;
        RejectedCandidate *n = realloc(list->items, ncap * sizeof(*n));
        if (!n) {
            return -1;
        }
        list->items = n;
        list->cap = ncap;
    }
    RejectedCandidate *r = &list->items[list->count++];
    snprintf(r->candidate_key, sizeof(r->candidate_key), "%s", key);
    snprintf(r->reason, sizeof(r->reason), "%s", reason);
    return 0;
}

static char *read_file(const char *path) {
    FILE *f = fopen(path, "rb");
    if (!f) {
        return NULL;
    }
    if (fseek(f, 0, SEEK_END) != 0) {
        fclose(f);
        return NULL;
    }
    long n = ftell(f);
    if (n < 0) {
        fclose(f);
        return NULL;
    }
    rewind(f);
    char *buf = malloc((size_t)n + 1);
    if (!buf) {
        fclose(f);
        return NULL;
    }
    if (fread(buf, 1, (size_t)n, f) != (size_t)n) {
        free(buf);
        fclose(f);
        return NULL;
    }
    buf[n] = '\0';
    fclose(f);
    return buf;
}

static void strip_html_comments(char *s) {
    char *dst = s;
    char *src = s;
    while (*src) {
        if (src[0] == '<' && src[1] == '!' && src[2] == '-' && src[3] == '-') {
            src += 4;
            while (*src && !(src[0] == '-' && src[1] == '-' && src[2] == '>')) {
                src++;
            }
            if (*src) {
                src += 3;
            }
            continue;
        }
        *dst++ = *src++;
    }
    *dst = '\0';
}

static void trim(char *s) {
    char *a = s;
    while (*a && isspace((unsigned char)*a)) {
        a++;
    }
    if (a != s) {
        memmove(s, a, strlen(a) + 1);
    }
    size_t n = strlen(s);
    while (n > 0 && isspace((unsigned char)s[n - 1])) {
        s[--n] = '\0';
    }
}

static int split_row(char *line, char **cols, int max_cols) {
    int n = 0;
    char *p = line;
    if (*p == '|') {
        p++;
    }
    while (*p && n < max_cols) {
        char *start = p;
        while (*p && *p != '|') {
            p++;
        }
        char saved = *p;
        *p = '\0';
        trim(start);
        cols[n++] = start;
        if (!saved) {
            break;
        }
        p++;
    }
    if (n > 0 && cols[n - 1][0] == '\0') {
        n--;
    }
    return n;
}

static int is_sep_row(char **cols, int ncols) {
    for (int i = 0; i < ncols; i++) {
        const char *c = cols[i];
        if (!*c) {
            return 0;
        }
        for (const char *p = c; *p; p++) {
            if (*p != '-' && *p != ':' && !isspace((unsigned char)*p)) {
                return 0;
            }
        }
    }
    return 1;
}

static int ci_eq(const char *a, const char *b) {
    while (*a && *b) {
        if (tolower((unsigned char)*a) != tolower((unsigned char)*b)) {
            return 0;
        }
        a++;
        b++;
    }
    return *a == '\0' && *b == '\0';
}

static int unit_scale(const char *units, int which, double *scale) {
    /* which: 0=k, 1=t0, 2=q */
    if (which == 0) {
        if (ci_eq(units, "Da_per_us2") || ci_eq(units, "Da/us^2")) {
            *scale = 1.0;
            return 0;
        }
        if (ci_eq(units, "mDa_per_us2") || ci_eq(units, "mDa/us^2")) {
            *scale = 1.0 / 1000.0;
            return 0;
        }
    } else if (which == 1) {
        if (ci_eq(units, "us")) {
            *scale = 1.0;
            return 0;
        }
        if (ci_eq(units, "ns")) {
            *scale = 1.0 / 1000.0;
            return 0;
        }
    } else if (which == 2) {
        if (ci_eq(units, "Da_per_us3") || ci_eq(units, "Da/us^3")) {
            *scale = 1.0;
            return 0;
        }
    }
    return -1;
}

static void make_row_serial(char *buf, size_t cap, const LabCandidate *c) {
    snprintf(buf, cap,
             "candidate_id=%s|rev=%d|k=%.12e|t0=%.12e|q=%.12e|"
             "c00=%.12e|c01=%.12e|c02=%.12e|c11=%.12e|c12=%.12e|c22=%.12e",
             c->candidate_id, c->rev, c->theta.v[0], c->theta.v[1], c->theta.v[2],
             c->cov.m[0][0], c->cov.m[0][1], c->cov.m[0][2], c->cov.m[1][1],
             c->cov.m[1][2], c->cov.m[2][2]);
}

static int better_candidate(const LabCandidate *a, const LabCandidate *b) {
    if (a->rev != b->rev) {
        return a->rev > b->rev;
    }
    if (a->gscale < b->gscale) {
        return 1;
    }
    if (a->gscale > b->gscale) {
        return 0;
    }
    return strcmp(a->row_serial, b->row_serial) < 0;
}

typedef struct {
    LabCandidate *items;
    size_t count;
    size_t cap;
} RawList;

static int raw_push(RawList *list, const LabCandidate *item) {
    if (list->count + 1 > list->cap) {
        size_t ncap = list->cap ? list->cap * 2 : 8;
        LabCandidate *n = realloc(list->items, ncap * sizeof(*n));
        if (!n) {
            return -1;
        }
        list->items = n;
        list->cap = ncap;
    }
    list->items[list->count++] = *item;
    return 0;
}

static int parse_file(const char *path, const char *rel, RawList *raw,
                      RejectedList *rejected) {
    char *text = read_file(path);
    if (!text) {
        return -1;
    }
    strip_html_comments(text);

    char *saveptr = NULL;
    char *line = strtok_r(text, "\n", &saveptr);
    int in_axis = 0;
    int header_ok = 0;
    int col_index[16];
    for (int i = 0; i < 16; i++) {
        col_index[i] = -1;
    }
    const char *need[] = {
        "candidate_id", "rev", "status", "k", "t0", "q", "sigma_k", "sigma_t0",
        "sigma_q", "rho_k_t0", "rho_k_q", "rho_t0_q", "k_units", "t0_units",
        "q_units"};

    while (line) {
        char *trimline = line;
        while (*trimline && isspace((unsigned char)*trimline)) {
            trimline++;
        }
        if (strncmp(trimline, "##", 2) == 0) {
            in_axis = strstr(trimline, "axis_candidate") != NULL;
            header_ok = 0;
            for (int i = 0; i < 16; i++) {
                col_index[i] = -1;
            }
            line = strtok_r(NULL, "\n", &saveptr);
            continue;
        }
        if (!in_axis || trimline[0] != '|') {
            line = strtok_r(NULL, "\n", &saveptr);
            continue;
        }

        char rowbuf[4096];
        snprintf(rowbuf, sizeof(rowbuf), "%s", trimline);
        char *cols[32];
        int ncols = split_row(rowbuf, cols, 32);
        if (ncols <= 0) {
            line = strtok_r(NULL, "\n", &saveptr);
            continue;
        }
        if (!header_ok) {
            if (is_sep_row(cols, ncols)) {
                line = strtok_r(NULL, "\n", &saveptr);
                continue;
            }
            for (int i = 0; i < ncols; i++) {
                for (int k = 0; k < 15; k++) {
                    if (ci_eq(cols[i], need[k])) {
                        col_index[k] = i;
                    }
                }
            }
            int missing = 0;
            for (int k = 0; k < 15; k++) {
                if (col_index[k] < 0) {
                    missing = 1;
                }
            }
            header_ok = !missing;
            line = strtok_r(NULL, "\n", &saveptr);
            continue;
        }
        if (is_sep_row(cols, ncols)) {
            line = strtok_r(NULL, "\n", &saveptr);
            continue;
        }

        const char *status = cols[col_index[2]];
        if (!ci_eq(status, "active")) {
            line = strtok_r(NULL, "\n", &saveptr);
            continue;
        }

        LabCandidate cand;
        memset(&cand, 0, sizeof(cand));
        snprintf(cand.candidate_id, sizeof(cand.candidate_id), "%s",
                 cols[col_index[0]]);
        cand.rev = atoi(cols[col_index[1]]);
        snprintf(cand.source_file, sizeof(cand.source_file), "%s", rel);

        double k = atof(cols[col_index[3]]);
        double t0 = atof(cols[col_index[4]]);
        double q = atof(cols[col_index[5]]);
        double sk = atof(cols[col_index[6]]);
        double st0 = atof(cols[col_index[7]]);
        double sq = atof(cols[col_index[8]]);
        double rkt0 = atof(cols[col_index[9]]);
        double rkq = atof(cols[col_index[10]]);
        double rt0q = atof(cols[col_index[11]]);
        const char *ku = cols[col_index[12]];
        const char *tu = cols[col_index[13]];
        const char *qu = cols[col_index[14]];

        snprintf(cand.candidate_key, sizeof(cand.candidate_key), "%s::%s@%d", rel,
                 cand.candidate_id, cand.rev);

        int invalid = 0;
        if (!isfinite(k) || !isfinite(t0) || !isfinite(q) || !isfinite(sk) ||
            !isfinite(st0) || !isfinite(sq) || !isfinite(rkt0) || !isfinite(rkq) ||
            !isfinite(rt0q)) {
            invalid = 1;
        }
        if (!(sk > 0.0) || !(st0 > 0.0) || !(sq > 0.0)) {
            invalid = 1;
        }
        if (rkt0 < -1.0 || rkt0 > 1.0 || rkq < -1.0 || rkq > 1.0 || rt0q < -1.0 ||
            rt0q > 1.0) {
            invalid = 1;
        }
        double sk_s, st0_s, sq_s;
        if (unit_scale(ku, 0, &sk_s) || unit_scale(tu, 1, &st0_s) ||
            unit_scale(qu, 2, &sq_s)) {
            invalid = 1;
        }

        if (!invalid) {
            cand.theta.v[0] = k;
            cand.theta.v[1] = t0;
            cand.theta.v[2] = q;
            cov_from_sigmas(&cand.cov, sk, st0, sq, rkt0, rkq, rt0q);
            apply_unit_scale(&cand.theta, &cand.cov, sk_s, st0_s, sq_s);
            if (!mat3_is_spd(&cand.cov)) {
                invalid = 1;
            } else {
                cand.gscale = mat3_gscale(&cand.cov);
                make_row_serial(cand.row_serial, sizeof(cand.row_serial), &cand);
            }
        }

        if (invalid) {
            rejected_list_push(rejected, cand.candidate_key, "invalid_covariance");
        } else {
            raw_push(raw, &cand);
        }

        line = strtok_r(NULL, "\n", &saveptr);
    }

    free(text);
    return 0;
}

static int collect_md(const char *dir, const char *rel_prefix, char ***paths,
                      char ***rels, size_t *n, size_t *cap) {
    DIR *d = opendir(dir);
    if (!d) {
        return -1;
    }
    struct dirent *ent;
    while ((ent = readdir(d)) != NULL) {
        if (strcmp(ent->d_name, ".") == 0 || strcmp(ent->d_name, "..") == 0) {
            continue;
        }
        char path[1024];
        char rel[1024];
        snprintf(path, sizeof(path), "%s/%s", dir, ent->d_name);
        if (rel_prefix[0]) {
            snprintf(rel, sizeof(rel), "%s/%s", rel_prefix, ent->d_name);
        } else {
            snprintf(rel, sizeof(rel), "%s", ent->d_name);
        }
        struct stat st;
        if (stat(path, &st) != 0) {
            continue;
        }
        if (S_ISDIR(st.st_mode)) {
            if (collect_md(path, rel, paths, rels, n, cap) != 0) {
                closedir(d);
                return -1;
            }
        } else {
            size_t len = strlen(ent->d_name);
            if (len < 4 || strcmp(ent->d_name + len - 3, ".md") != 0) {
                continue;
            }
            if (*n + 1 > *cap) {
                size_t ncap = *cap ? *cap * 2 : 8;
                char **np = realloc(*paths, ncap * sizeof(char *));
                char **nr = realloc(*rels, ncap * sizeof(char *));
                if (!np || !nr) {
                    closedir(d);
                    return -1;
                }
                *paths = np;
                *rels = nr;
                *cap = ncap;
            }
            (*paths)[*n] = strdup(path);
            (*rels)[*n] = strdup(rel);
            (*n)++;
        }
    }
    closedir(d);
    return 0;
}

int parse_lab_notes(const char *notes_dir, LabCandidateList *out,
                    RejectedList *rejected) {
    char **paths = NULL;
    char **rels = NULL;
    size_t n = 0, cap = 0;
    if (collect_md(notes_dir, "", &paths, &rels, &n, &cap) != 0) {
        return -1;
    }

    /* Sort by relative path for deterministic superseded recording order only;
     * selection itself is order-invariant. */
    for (size_t i = 0; i + 1 < n; i++) {
        for (size_t j = i + 1; j < n; j++) {
            if (strcmp(rels[i], rels[j]) > 0) {
                char *tp = paths[i];
                paths[i] = paths[j];
                paths[j] = tp;
                char *tr = rels[i];
                rels[i] = rels[j];
                rels[j] = tr;
            }
        }
    }

    RawList raw = {0};
    for (size_t i = 0; i < n; i++) {
        if (parse_file(paths[i], rels[i], &raw, rejected) != 0) {
            free(raw.items);
            for (size_t k = 0; k < n; k++) {
                free(paths[k]);
                free(rels[k]);
            }
            free(paths);
            free(rels);
            return -1;
        }
    }

    int *taken = calloc(raw.count ? raw.count : 1, sizeof(int));
    if (!taken) {
        free(raw.items);
        for (size_t i = 0; i < n; i++) {
            free(paths[i]);
            free(rels[i]);
        }
        free(paths);
        free(rels);
        return -1;
    }
    for (size_t i = 0; i < raw.count; i++) {
        if (taken[i]) {
            continue;
        }
        int best = (int)i;
        for (size_t j = i + 1; j < raw.count; j++) {
            if (taken[j]) {
                continue;
            }
            if (strcmp(raw.items[j].source_file, raw.items[i].source_file) != 0) {
                continue;
            }
            if (strcmp(raw.items[j].candidate_id, raw.items[i].candidate_id) != 0) {
                continue;
            }
            if (better_candidate(&raw.items[j], &raw.items[best])) {
                best = (int)j;
            }
        }
        for (size_t j = 0; j < raw.count; j++) {
            if (strcmp(raw.items[j].source_file, raw.items[i].source_file) != 0) {
                continue;
            }
            if (strcmp(raw.items[j].candidate_id, raw.items[i].candidate_id) != 0) {
                continue;
            }
            taken[j] = 1;
            if ((int)j == best) {
                continue;
            }
            rejected_list_push(rejected, raw.items[j].candidate_key, "superseded");
        }
        lab_list_push(out, &raw.items[best]);
    }
    free(taken);

    free(raw.items);
    for (size_t i = 0; i < n; i++) {
        free(paths[i]);
        free(rels[i]);
    }
    free(paths);
    free(rels);
    return 0;
}
