#ifndef OBS_H
#define OBS_H

#include <stddef.h>
#include <stdint.h>

typedef struct {
    uint32_t window_id;
    uint64_t start_tick;
    double nominal_dt_ns;
    uint16_t sample_count;
    uint16_t present_count;
    float scale;
    float offset;
    unsigned char *present;
    double *time_s;
    double *value;
} ObsWindow;

typedef struct {
    uint32_t instrument_id;
    size_t window_count;
    ObsWindow *windows;
} ObservationBundle;

typedef struct {
    size_t count;
    ObservationBundle *bundles;
} ObservationSet;

int load_observations(const char *dir, ObservationSet *out);
void free_observations(ObservationSet *set);

#endif
