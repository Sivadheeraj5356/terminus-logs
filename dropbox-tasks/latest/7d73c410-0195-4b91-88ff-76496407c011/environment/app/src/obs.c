#define _DEFAULT_SOURCE

#include "obs.h"

#include <dirent.h>
#include <errno.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static uint16_t read_u16_be(FILE *f, int *ok) {
    unsigned char b[2];
    if (fread(b, 1, 2, f) != 2) {
        *ok = 0;
        return 0;
    }
    return (uint16_t)((uint16_t)b[0] << 8 | b[1]);
}

static uint16_t read_u16_le(FILE *f, int *ok) {
    unsigned char b[2];
    if (fread(b, 1, 2, f) != 2) {
        *ok = 0;
        return 0;
    }
    return (uint16_t)((uint16_t)b[1] << 8 | b[0]);
}

static uint32_t read_u32_be(FILE *f, int *ok) {
    unsigned char b[4];
    if (fread(b, 1, 4, f) != 4) {
        *ok = 0;
        return 0;
    }
    return ((uint32_t)b[0] << 24) | ((uint32_t)b[1] << 16) | ((uint32_t)b[2] << 8) | b[3];
}

static uint64_t read_u64_le(FILE *f, int *ok) {
    unsigned char b[8];
    if (fread(b, 1, 8, f) != 8) {
        *ok = 0;
        return 0;
    }
    uint64_t v = 0;
    for (int i = 7; i >= 0; i--) v = (v << 8) | b[i];
    return v;
}

static double read_f64_le(FILE *f, int *ok) {
    uint64_t bits = read_u64_le(f, ok);
    double value = 0.0;
    if (*ok) memcpy(&value, &bits, sizeof(value));
    return value;
}

static float read_f32_le(FILE *f, int *ok) {
    unsigned char b[4];
    if (fread(b, 1, 4, f) != 4) {
        *ok = 0;
        return 0.0f;
    }
    uint32_t bits = ((uint32_t)b[3] << 24) | ((uint32_t)b[2] << 16) | ((uint32_t)b[1] << 8) | b[0];
    float value = 0.0f;
    memcpy(&value, &bits, sizeof(value));
    return value;
}

static int has_ext(const char *name, const char *ext) {
    size_t n = strlen(name);
    size_t e = strlen(ext);
    return n >= e && strcmp(name + n - e, ext) == 0;
}

static int mask_bit(const unsigned char *mask, size_t i) {
    return (mask[i / 8] >> (i % 8)) & 1U;
}

static int load_bundle_file(const char *path, ObservationBundle *bundle) {
    FILE *f = fopen(path, "rb");
    if (!f) return -1;

    int ok = 1;
    unsigned char magic[4];
    if (fread(magic, 1, 4, f) != 4 || memcmp(magic, "ASE1", 4) != 0) ok = 0;
    int version = fgetc(f);
    if (version != 2) ok = 0;

    bundle->instrument_id = read_u32_be(f, &ok);
    bundle->window_count = read_u16_le(f, &ok);
    (void)read_u16_le(f, &ok);
    bundle->windows = calloc(bundle->window_count, sizeof(*bundle->windows));
    if (!bundle->windows) ok = 0;

    for (size_t w = 0; ok && w < bundle->window_count; w++) {
        ObsWindow *win = &bundle->windows[w];
        win->window_id = read_u32_be(f, &ok);
        win->start_tick = read_u64_le(f, &ok);
        win->nominal_dt_ns = read_f64_le(f, &ok);
        win->sample_count = read_u16_be(f, &ok);
        win->present_count = read_u16_be(f, &ok);
        win->scale = read_f32_le(f, &ok);
        win->offset = read_f32_le(f, &ok);

        size_t mask_len = (win->sample_count + 7U) / 8U;
        unsigned char *mask = malloc(mask_len);
        win->present = calloc(win->sample_count, sizeof(*win->present));
        win->time_s = calloc(win->present_count, sizeof(*win->time_s));
        win->value = calloc(win->present_count, sizeof(*win->value));
        if (!mask || !win->present || !win->time_s || !win->value) ok = 0;
        if (ok && fread(mask, 1, mask_len, f) != mask_len) ok = 0;

        size_t p = 0;
        for (size_t i = 0; ok && i < win->sample_count; i++) {
            if (!mask_bit(mask, i)) continue;
            win->present[i] = 1;
            int16_t raw = (int16_t)read_u16_be(f, &ok);
            if (!ok) break;
            win->time_s[p] = (double)win->start_tick * 1e-9 + (double)i * win->nominal_dt_ns * 1e-9;
            win->value[p] = (double)win->scale * (double)raw + (double)win->offset;
            p++;
        }
        if (p != win->present_count) ok = 0;
        free(mask);
    }

    fclose(f);
    if (!ok) {
        free(bundle->windows);
        memset(bundle, 0, sizeof(*bundle));
        return -1;
    }
    return 0;
}

int load_observations(const char *dir, ObservationSet *out) {
    memset(out, 0, sizeof(*out));
    DIR *d = opendir(dir);
    if (!d) return -1;

    struct dirent *ent;
    while ((ent = readdir(d)) != NULL) {
        if (has_ext(ent->d_name, ".ase")) out->count++;
    }
    rewinddir(d);

    out->bundles = calloc(out->count, sizeof(*out->bundles));
    if (out->count && !out->bundles) {
        closedir(d);
        return -1;
    }

    size_t i = 0;
    while ((ent = readdir(d)) != NULL) {
        if (!has_ext(ent->d_name, ".ase")) continue;
        char path[4096];
        snprintf(path, sizeof(path), "%s/%s", dir, ent->d_name);
        if (load_bundle_file(path, &out->bundles[i++]) != 0) {
            closedir(d);
            free_observations(out);
            return -1;
        }
    }

    closedir(d);
    return 0;
}

void free_observations(ObservationSet *set) {
    for (size_t b = 0; b < set->count; b++) {
        ObservationBundle *bundle = &set->bundles[b];
        for (size_t w = 0; w < bundle->window_count; w++) {
            free(bundle->windows[w].present);
            free(bundle->windows[w].time_s);
            free(bundle->windows[w].value);
        }
        free(bundle->windows);
    }
    free(set->bundles);
    memset(set, 0, sizeof(*set));
}
