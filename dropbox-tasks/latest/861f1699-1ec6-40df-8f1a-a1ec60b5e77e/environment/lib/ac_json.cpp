#include "ac_json.h"

#include <cstdio>

int ac_write_formant_json(const char *path, const ac_formant_report *rep) {
    FILE *fp = fopen(path, "w");
    if (!fp) {
        return -1;
    }
    fprintf(fp, "{\n");
    fprintf(fp, "  \"profile\": \"%s\",\n", rep->profile);
    fprintf(fp, "  \"sample_rate_hz\": %d,\n", rep->sample_rate_hz);
    fprintf(fp, "  \"formant_count\": %d,\n", rep->formant_count);
    fprintf(fp, "  \"formants_hz\": [");
    for (int i = 0; i < rep->formant_count; ++i) {
        if (i) {
            fputc(',', fp);
        }
        fprintf(fp, "%.3f", rep->formants_hz[i]);
    }
    fprintf(fp, "],\n");
    fprintf(fp, "  \"peak_prominence_db\": %.3f,\n", rep->peak_prominence_db);
    fprintf(fp, "  \"pressure_digest\": \"%s\",\n", rep->pressure_digest);
    fprintf(fp, "  \"cavity_speed_digest\": \"%s\"\n", rep->cavity_speed_digest);
    fprintf(fp, "}\n");
    fclose(fp);
    return 0;
}

int ac_write_summary_json(const char *path, const char **profiles, int n) {
    FILE *fp = fopen(path, "w");
    if (!fp) {
        return -1;
    }
    fprintf(fp, "{\n  \"profiles\": [");
    for (int i = 0; i < n; ++i) {
        if (i) {
            fputc(',', fp);
        }
        fprintf(fp, "\"%s\"", profiles[i]);
    }
    fprintf(fp, "],\n  \"batch_digest\": \"");
    for (int i = 0; i < n; ++i) {
        if (i) {
            fputc(',', fp);
        }
        fputs(profiles[i], fp);
    }
    fprintf(fp, "\"\n}\n");
    fclose(fp);
    return 0;
}
