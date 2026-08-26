#include "cryovac/calibrate.h"
#include "cryovac/cJSON.h"

#include <ctype.h>
#include <stdio.h>
#include <string.h>

static void strip_crlf(char *line) {
    size_t n = strlen(line);
    while (n > 0 && (line[n - 1] == '\n' || line[n - 1] == '\r')) {
        line[--n] = '\0';
    }
}

static int line_is_blank(const char *line) {
    for (const char *p = line; *p; p++) {
        if (!isspace((unsigned char)*p)) {
            return 0;
        }
    }
    return 1;
}

static int parse_leg(cJSON *obj, CvCalRow *row) {
    cJSON *leg = cJSON_GetObjectItemCaseSensitive(obj, "leg");
    if (!leg || cJSON_IsNull(leg)) {
        row->leg = -1;
        return 1;
    }
    if (!cJSON_IsString(leg) || !leg->valuestring) {
        return 0;
    }
    if (strcmp(leg->valuestring, "descend") == 0) {
        row->leg = CV_LEG_DESCEND;
        return 1;
    }
    if (strcmp(leg->valuestring, "ascend") == 0) {
        row->leg = CV_LEG_ASCEND;
        return 1;
    }
    return 0;
}

static int parse_row(cJSON *obj, CvCalRow *row) {
    memset(row, 0, sizeof(*row));
    cJSON *seq = cJSON_GetObjectItemCaseSensitive(obj, "seq");
    cJSON *kn2 = cJSON_GetObjectItemCaseSensitive(obj, "K_n2");
    cJSON *khe = cJSON_GetObjectItemCaseSensitive(obj, "K_he");
    cJSON *sites = cJSON_GetObjectItemCaseSensitive(obj, "n_sites");
    if (!cJSON_IsNumber(seq) || !cJSON_IsNumber(kn2) || !cJSON_IsNumber(khe) || !cJSON_IsNumber(sites)) {
        return 0;
    }
    row->seq = seq->valueint;
    row->K_n2 = kn2->valuedouble;
    row->K_he = khe->valuedouble;
    row->n_sites = sites->valuedouble;
    if (!parse_leg(obj, row)) {
        return 0;
    }
    cJSON *req = cJSON_GetObjectItemCaseSensitive(obj, "requires_prev_seq");
    row->requires_prev_seq = cJSON_IsNumber(req) ? req->valueint : -1;

    cJSON *uni = cJSON_GetObjectItemCaseSensitive(obj, "universal");
    if (cJSON_IsTrue(uni)) {
        row->universal = 1;
    } else {
        cJSON *tmin = cJSON_GetObjectItemCaseSensitive(obj, "t_min");
        cJSON *tmax = cJSON_GetObjectItemCaseSensitive(obj, "t_max");
        if (!cJSON_IsNumber(tmin) || !cJSON_IsNumber(tmax) || tmin->valuedouble > tmax->valuedouble) {
            return 0;
        }
        row->t_min = tmin->valuedouble;
        row->t_max = tmax->valuedouble;
        row->universal = 0;
    }
    row->valid = (row->K_n2 > 0.0 && row->K_he >= 0.0 && row->n_sites > 0.0) ? 1 : 0;
    return 1;
}

int cv_load_cal_table(const char *path, CvCalTable *out) {
    memset(out, 0, sizeof(*out));
    FILE *f = fopen(path, "rb");
    if (!f) {
        return -1;
    }
    char line[2048];
    while (fgets(line, sizeof(line), f)) {
        strip_crlf(line);
        if (line_is_blank(line)) {
            continue;
        }
        cJSON *obj = cJSON_Parse(line);
        if (!obj) {
            fclose(f);
            return -1;
        }
        if (out->count >= CV_MAX_CAL) {
            cJSON_Delete(obj);
            fclose(f);
            return -1;
        }
        CvCalRow row;
        if (!parse_row(obj, &row)) {
            cJSON_Delete(obj);
            fclose(f);
            return -1;
        }
        out->rows[out->count++] = row;
        cJSON_Delete(obj);
    }
    fclose(f);
    return out->count > 0 ? 0 : -1;
}

static int better_bounded(const CvCalRow *a, const CvCalRow *b) {
    if (a->seq != b->seq) {
        return a->seq > b->seq;
    }
    double wa = a->t_max - a->t_min;
    double wb = b->t_max - b->t_min;
    if (wa != wb) {
        return wa < wb;
    }
    if (a->n_sites != b->n_sites) {
        return a->n_sites > b->n_sites;
    }
    return a->t_min < b->t_min;
}

static int pred_ok(const CvCalRow *r, int prev_cal_seq) {
    if (r->requires_prev_seq < 0) {
        return 1;
    }
    return r->requires_prev_seq == prev_cal_seq;
}

static int bounded_covers(const CvCalRow *r, double temp_k, int leg, int prev_cal_seq) {
    if (!r->valid || r->universal) {
        return 0;
    }
    if (temp_k < r->t_min || temp_k > r->t_max) {
        return 0;
    }
    if (r->leg != -1 && r->leg != leg) {
        return 0;
    }
    if (!pred_ok(r, prev_cal_seq)) {
        return 0;
    }
    return 1;
}

static int any_bounded_cover(const CvCalTable *table, double temp_k, int leg, int prev_cal_seq) {
    for (int i = 0; i < table->count; i++) {
        if (bounded_covers(&table->rows[i], temp_k, leg, prev_cal_seq)) {
            return 1;
        }
    }
    return 0;
}

const CvCalRow *cv_find_seq(const CvCalTable *table, int seq) {
    const CvCalRow *best = NULL;
    for (int i = 0; i < table->count; i++) {
        const CvCalRow *r = &table->rows[i];
        if (!r->valid || r->seq != seq) {
            continue;
        }
        if (!best || better_bounded(r, best)) {
            best = r;
        }
    }
    return best;
}

int cv_sticky_eligible(const CvCalTable *table, const CvCalRow *row, double temp_k, int leg,
                       int prev_cal_seq) {
    if (!row || !row->valid) {
        return 0;
    }
    if (row->universal) {
        return !any_bounded_cover(table, temp_k, leg, prev_cal_seq);
    }
    if (temp_k < row->t_min || temp_k > row->t_max) {
        return 0;
    }
    if (row->leg != -1 && row->leg != leg) {
        return 0;
    }
    return 1;
}

int cv_resolve_sorption(const CvCalTable *table, double temp_k, int leg, int prev_cal_seq,
                        CvSorption *out, int *seq_out) {
    int best_cover = -1;
    int best_uni = -1;
    for (int i = 0; i < table->count; i++) {
        const CvCalRow *r = &table->rows[i];
        if (!r->valid) {
            continue;
        }
        if (r->universal) {
            if (best_uni < 0 || r->seq > table->rows[best_uni].seq ||
                (r->seq == table->rows[best_uni].seq && r->n_sites > table->rows[best_uni].n_sites)) {
                best_uni = i;
            }
            continue;
        }
        if (!bounded_covers(r, temp_k, leg, prev_cal_seq)) {
            continue;
        }
        if (best_cover < 0 || better_bounded(r, &table->rows[best_cover])) {
            best_cover = i;
        }
    }
    int pick = best_cover >= 0 ? best_cover : best_uni;
    if (pick < 0) {
        return -1;
    }
    out->K_n2 = table->rows[pick].K_n2;
    out->K_he = table->rows[pick].K_he;
    out->n_sites = table->rows[pick].n_sites;
    if (seq_out) {
        *seq_out = table->rows[pick].seq;
    }
    return 0;
}
