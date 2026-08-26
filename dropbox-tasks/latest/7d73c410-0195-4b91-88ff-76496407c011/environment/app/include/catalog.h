#ifndef CATALOG_H
#define CATALOG_H

#include <stddef.h>
#include <stdint.h>

typedef struct {
    uint32_t instrument_id;
    char code[16];
    double sample_rate_hz;
    double clock_ppm;
    double phase_offset_rad;
    double noise_floor;
} Instrument;

typedef struct {
    char label[32];
    double f0_hz;
    double chirp_hz_per_s;
    double start_s;
    double end_s;
} CalibrationLine;

typedef struct {
    uint32_t window_id;
    double start_s;
    double end_s;
    double weight;
} SurveyWindow;

typedef struct {
    size_t instrument_count;
    Instrument *instruments;
    size_t calibration_count;
    CalibrationLine *calibrations;
    size_t survey_window_count;
    SurveyWindow *survey_windows;
} Catalog;

int load_catalog(const char *path, Catalog *out);
const Instrument *find_instrument(const Catalog *catalog, uint32_t instrument_id);
const SurveyWindow *find_survey_window(const Catalog *catalog, uint32_t window_id);
void free_catalog(Catalog *catalog);

#endif
