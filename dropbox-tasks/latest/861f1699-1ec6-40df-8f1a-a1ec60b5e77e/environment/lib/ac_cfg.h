#ifndef AC_CFG_H
#define AC_CFG_H

struct ac_lab_cfg {
    int sample_rate_hz;
    double formant_min_hz;
    double formant_max_hz;
    double peak_min_db;
    double peak_min_sep_hz;
    int formant_tolerance_hz;
    int bridge_x;
    int bridge_y;
    int mic_x;
    int mic_y;
};

int ac_load_lab_cfg(const char *path, ac_lab_cfg *cfg);

#endif
