#include "ac_cfg.h"

#include "ac_limits.h"

#include <cstdio>
#include <cstdlib>
#include <cstring>

static int read_int(const char *line, const char *key, int *out) {
    const char *p = strstr(line, key);
    if (!p) {
        return -1;
    }
    p = strchr(p, '=');
    if (!p) {
        return -1;
    }
    *out = static_cast<int>(strtol(p + 1, nullptr, 10));
    return 0;
}

static int read_double(const char *line, const char *key, double *out) {
    const char *p = strstr(line, key);
    if (!p) {
        return -1;
    }
    p = strchr(p, '=');
    if (!p) {
        return -1;
    }
    *out = strtod(p + 1, nullptr);
    return 0;
}

int ac_load_lab_cfg(const char *path, ac_lab_cfg *cfg) {
    cfg->sample_rate_hz = AC_SR_HZ;
    cfg->formant_min_hz = AC_FORMANT_MIN_HZ;
    cfg->formant_max_hz = AC_FORMANT_MAX_HZ;
    cfg->peak_min_db = AC_PEAK_MIN_DB;
    cfg->peak_min_sep_hz = AC_PEAK_MIN_SEP_HZ;
    cfg->formant_tolerance_hz = 5;
    cfg->bridge_x = AC_BRIDGE_X;
    cfg->bridge_y = AC_BRIDGE_Y;
    cfg->mic_x = AC_MIC_X;
    cfg->mic_y = AC_MIC_Y;

    FILE *fp = fopen(path, "r");
    if (!fp) {
        return 0;
    }
    char line[256];
    while (fgets(line, sizeof line, fp)) {
        read_int(line, "sample_rate_hz", &cfg->sample_rate_hz);
        read_double(line, "formant_min_hz", &cfg->formant_min_hz);
        read_double(line, "formant_max_hz", &cfg->formant_max_hz);
        read_double(line, "peak_min_db", &cfg->peak_min_db);
        read_double(line, "peak_min_sep_hz", &cfg->peak_min_sep_hz);
        read_int(line, "formant_tolerance_hz", &cfg->formant_tolerance_hz);
        read_int(line, "bridge_x", &cfg->bridge_x);
        read_int(line, "bridge_y", &cfg->bridge_y);
        read_int(line, "mic_x", &cfg->mic_x);
        read_int(line, "mic_y", &cfg->mic_y);
    }
    fclose(fp);
    return 0;
}
