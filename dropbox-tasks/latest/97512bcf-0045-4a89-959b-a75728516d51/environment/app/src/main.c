#include "cryovac/calibrate.h"
#include "cryovac/chamber.h"
#include "cryovac/cli.h"
#include "cryovac/cJSON.h"
#include "cryovac/types.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define MAX_STEPS CV_MAX_STEPS

typedef struct {
    double t;
    double temp_k;
} TempStep;

typedef struct {
    double n_n2;
    double n_he;
    int count;
    TempStep steps[MAX_STEPS];
} Profile;

static int load_chamber_toml(const char *path, CvSolverCfg *out) {
    out->max_solver_iters = 1;
    out->ads_tol = 1.0e-4;
    out->cond_tol = 1.0e-4;
    FILE *f = fopen(path, "rb");
    if (!f) {
        return -1;
    }
    char line[512];
    while (fgets(line, sizeof(line), f)) {
        char *p = line;
        while (*p == ' ' || *p == '\t') {
            p++;
        }
        if (*p == '#' || *p == '\0' || *p == '\n' || *p == '\r') {
            continue;
        }
        char key[64];
        char val[64];
        if (sscanf(p, "%63s = %63s", key, val) != 2) {
            continue;
        }
        if (strcmp(key, "max_solver_iters") == 0) {
            out->max_solver_iters = atoi(val);
        } else if (strcmp(key, "ads_tol") == 0) {
            out->ads_tol = atof(val);
        } else if (strcmp(key, "cond_tol") == 0) {
            out->cond_tol = atof(val);
        }
    }
    fclose(f);
    return out->max_solver_iters > 0 ? 0 : -1;
}

static int load_species_pair(CvSpecies *n2, CvSpecies *he) {
    FILE *f = fopen("/app/config/species.json", "rb");
    if (!f) {
        return -1;
    }
    fseek(f, 0, SEEK_END);
    long sz = ftell(f);
    fseek(f, 0, SEEK_SET);
    char *buf = (char *)malloc((size_t)sz + 1);
    if (!buf) {
        fclose(f);
        return -1;
    }
    if (fread(buf, 1, (size_t)sz, f) != (size_t)sz) {
        free(buf);
        fclose(f);
        return -1;
    }
    fclose(f);
    buf[sz] = '\0';
    cJSON *root = cJSON_Parse(buf);
    free(buf);
    if (!root) {
        return -1;
    }

    cJSON *jn2 = cJSON_GetObjectItemCaseSensitive(root, "N2");
    cJSON *jhe = cJSON_GetObjectItemCaseSensitive(root, "He");
    if (!cJSON_IsObject(jn2) || !cJSON_IsObject(jhe)) {
        cJSON_Delete(root);
        return -1;
    }

    memset(n2, 0, sizeof(*n2));
    memset(he, 0, sizeof(*he));
    strncpy(n2->name, "N2", sizeof(n2->name) - 1);
    strncpy(he->name, "He", sizeof(he->name) - 1);
    n2->a = cJSON_GetObjectItemCaseSensitive(jn2, "a")->valuedouble;
    n2->b = cJSON_GetObjectItemCaseSensitive(jn2, "b")->valuedouble;
    n2->condensable = 1;
    n2->T_cond = cJSON_GetObjectItemCaseSensitive(jn2, "T_cond")->valuedouble;
    n2->T_freeze = cJSON_GetObjectItemCaseSensitive(jn2, "T_freeze")->valuedouble;
    n2->T_thaw = cJSON_GetObjectItemCaseSensitive(jn2, "T_thaw")->valuedouble;
    n2->P_vap_ref = cJSON_GetObjectItemCaseSensitive(jn2, "P_vap_ref")->valuedouble;
    n2->T_vap_ref = cJSON_GetObjectItemCaseSensitive(jn2, "T_vap_ref")->valuedouble;
    n2->L_vap = cJSON_GetObjectItemCaseSensitive(jn2, "L_vap")->valuedouble;
    cJSON *beta = cJSON_GetObjectItemCaseSensitive(jn2, "film_site_beta");
    n2->film_site_beta = cJSON_IsNumber(beta) ? beta->valuedouble : 0.0;
    cJSON *kappa = cJSON_GetObjectItemCaseSensitive(jn2, "kappa_film");
    n2->kappa_film = cJSON_IsNumber(kappa) ? kappa->valuedouble : 0.0;
    cJSON *vmin = cJSON_GetObjectItemCaseSensitive(jn2, "vmin_frac");
    n2->vmin_frac = cJSON_IsNumber(vmin) ? vmin->valuedouble : 0.05;

    he->a = cJSON_GetObjectItemCaseSensitive(jhe, "a")->valuedouble;
    he->b = cJSON_GetObjectItemCaseSensitive(jhe, "b")->valuedouble;
    he->condensable = 0;

    cJSON_Delete(root);
    return 0;
}

static int load_profile(const char *path, Profile *out) {
    memset(out, 0, sizeof(*out));
    FILE *f = fopen(path, "rb");
    if (!f) {
        return -1;
    }
    fseek(f, 0, SEEK_END);
    long sz = ftell(f);
    fseek(f, 0, SEEK_SET);
    char *buf = (char *)malloc((size_t)sz + 1);
    if (!buf) {
        fclose(f);
        return -1;
    }
    if (fread(buf, 1, (size_t)sz, f) != (size_t)sz) {
        free(buf);
        fclose(f);
        return -1;
    }
    fclose(f);
    buf[sz] = '\0';
    cJSON *root = cJSON_Parse(buf);
    free(buf);
    if (!root) {
        return -1;
    }
    cJSON *nn2 = cJSON_GetObjectItemCaseSensitive(root, "n_n2");
    cJSON *nhe = cJSON_GetObjectItemCaseSensitive(root, "n_he");
    cJSON *steps = cJSON_GetObjectItemCaseSensitive(root, "steps");
    if (!cJSON_IsNumber(nn2) || !cJSON_IsNumber(nhe) || !cJSON_IsArray(steps)) {
        cJSON_Delete(root);
        return -1;
    }
    out->n_n2 = nn2->valuedouble;
    out->n_he = nhe->valuedouble;
    cJSON *it = NULL;
    cJSON_ArrayForEach(it, steps) {
        if (out->count >= MAX_STEPS) {
            break;
        }
        cJSON *t = cJSON_GetObjectItemCaseSensitive(it, "t");
        cJSON *tk = cJSON_GetObjectItemCaseSensitive(it, "temp_k");
        if (!cJSON_IsNumber(t) || !cJSON_IsNumber(tk)) {
            cJSON_Delete(root);
            return -1;
        }
        out->steps[out->count].t = t->valuedouble;
        out->steps[out->count].temp_k = tk->valuedouble;
        out->count++;
    }
    cJSON_Delete(root);
    return out->count > 0 ? 0 : -1;
}

static int write_trace(const char *path, const CvChamber *ch, const CvStepOut *hist, int n) {
    cJSON *root = cJSON_CreateObject();
    cJSON_AddNumberToObject(root, "final_pressure_pa", hist[n - 1].p_total);
    cJSON_AddNumberToObject(root, "condensation_events", ch->condensation_events);
    cJSON_AddNumberToObject(root, "freeze_events", ch->freeze_events);
    cJSON *arr = cJSON_AddArrayToObject(root, "history");
    for (int i = 0; i < n; i++) {
        cJSON *row = cJSON_CreateObject();
        cJSON_AddNumberToObject(row, "t", hist[i].t);
        cJSON_AddNumberToObject(row, "temp_k", hist[i].temp_k);
        cJSON_AddNumberToObject(row, "p_total", hist[i].p_total);
        cJSON_AddNumberToObject(row, "n_gas_n2", hist[i].n_gas_n2);
        cJSON_AddNumberToObject(row, "n_gas_he", hist[i].n_gas_he);
        cJSON_AddNumberToObject(row, "n_ads_n2", hist[i].n_ads_n2);
        cJSON_AddNumberToObject(row, "n_ads_he", hist[i].n_ads_he);
        cJSON_AddNumberToObject(row, "n_cond_n2", hist[i].n_cond_n2);
        cJSON_AddNumberToObject(row, "x_he", hist[i].x_he);
        cJSON_AddBoolToObject(row, "frozen", hist[i].frozen);
        cJSON_AddNumberToObject(row, "cal_seq", hist[i].cal_seq);
        cJSON_AddNumberToObject(row, "solver_iters", hist[i].solver_iters);
        cJSON_AddNumberToObject(row, "thermal_leg", hist[i].thermal_leg);
        cJSON_AddStringToObject(row, "regime", hist[i].regime);
        cJSON_AddItemToArray(arr, row);
    }
    char *printed = cJSON_Print(root);
    cJSON_Delete(root);
    if (!printed) {
        return -1;
    }
    FILE *f = fopen(path, "wb");
    if (!f) {
        free(printed);
        return -1;
    }
    fputs(printed, f);
    fputc('\n', f);
    fclose(f);
    free(printed);
    return 0;
}

int main(int argc, char **argv) {
    CvCli cli;
    if (cv_parse_cli(argc, argv, &cli) != 0) {
        return 2;
    }

    Profile profile;
    if (load_profile(cli.profile, &profile) != 0) {
        fprintf(stderr, "failed to load profile\n");
        return 2;
    }

    CvSpecies n2, he;
    if (load_species_pair(&n2, &he) != 0) {
        fprintf(stderr, "failed to load species\n");
        return 2;
    }

    CvCalTable cal;
    if (cv_load_cal_table(cli.calibration, &cal) != 0) {
        fprintf(stderr, "failed to load sorption calibration\n");
        return 2;
    }

    CvSolverCfg solver;
    if (load_chamber_toml("/app/config/chamber.toml", &solver) != 0) {
        fprintf(stderr, "failed to load chamber.toml\n");
        return 2;
    }

    CvChamber chamber;
    cv_chamber_init(&chamber, profile.n_n2, profile.n_he, cli.volume_m3, &n2, &he, &cal, &solver);

    CvStepOut hist[MAX_STEPS];
    for (int i = 0; i < profile.count; i++) {
        if (cv_chamber_advance(&chamber, profile.steps[i].t, profile.steps[i].temp_k, &hist[i]) != 0) {
            fprintf(stderr, "advance failed at step %d\n", i);
            return 2;
        }
    }

    if (write_trace(cli.out, &chamber, hist, profile.count) != 0) {
        fprintf(stderr, "failed to write output\n");
        return 2;
    }
    return 0;
}
