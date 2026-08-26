#include "catalog.h"

#include <sqlite3.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int count_rows(sqlite3 *db, const char *table, size_t *out) {
    char sql[128];
    sqlite3_stmt *stmt = NULL;
    snprintf(sql, sizeof(sql), "SELECT COUNT(*) FROM %s", table);
    if (sqlite3_prepare_v2(db, sql, -1, &stmt, NULL) != SQLITE_OK) return -1;
    int rc = sqlite3_step(stmt);
    if (rc == SQLITE_ROW) {
        *out = (size_t)sqlite3_column_int64(stmt, 0);
        sqlite3_finalize(stmt);
        return 0;
    }
    sqlite3_finalize(stmt);
    return -1;
}

static int load_instruments(sqlite3 *db, Catalog *out) {
    sqlite3_stmt *stmt = NULL;
    if (count_rows(db, "instruments", &out->instrument_count) != 0) return -1;
    out->instruments = calloc(out->instrument_count, sizeof(*out->instruments));
    if (out->instrument_count && !out->instruments) return -1;

    const char *sql =
        "SELECT instrument_id, code, sample_rate_hz, clock_ppm, phase_offset_rad, noise_floor "
        "FROM instruments ORDER BY instrument_id";
    if (sqlite3_prepare_v2(db, sql, -1, &stmt, NULL) != SQLITE_OK) return -1;

    size_t i = 0;
    while (sqlite3_step(stmt) == SQLITE_ROW && i < out->instrument_count) {
        Instrument *inst = &out->instruments[i++];
        inst->instrument_id = (uint32_t)sqlite3_column_int(stmt, 0);
        snprintf(inst->code, sizeof(inst->code), "%s", sqlite3_column_text(stmt, 1));
        inst->sample_rate_hz = sqlite3_column_double(stmt, 2);
        inst->clock_ppm = sqlite3_column_double(stmt, 3);
        inst->phase_offset_rad = sqlite3_column_double(stmt, 4);
        inst->noise_floor = sqlite3_column_double(stmt, 5);
    }

    sqlite3_finalize(stmt);
    return i == out->instrument_count ? 0 : -1;
}

static int load_calibrations(sqlite3 *db, Catalog *out) {
    sqlite3_stmt *stmt = NULL;
    if (count_rows(db, "calibration_lines", &out->calibration_count) != 0) return -1;
    out->calibrations = calloc(out->calibration_count, sizeof(*out->calibrations));
    if (out->calibration_count && !out->calibrations) return -1;

    const char *sql =
        "SELECT label, f0_hz, chirp_hz_per_s, start_s, end_s "
        "FROM calibration_lines ORDER BY label";
    if (sqlite3_prepare_v2(db, sql, -1, &stmt, NULL) != SQLITE_OK) return -1;

    size_t i = 0;
    while (sqlite3_step(stmt) == SQLITE_ROW && i < out->calibration_count) {
        CalibrationLine *line = &out->calibrations[i++];
        snprintf(line->label, sizeof(line->label), "%s", sqlite3_column_text(stmt, 0));
        line->f0_hz = sqlite3_column_double(stmt, 1);
        line->chirp_hz_per_s = sqlite3_column_double(stmt, 2);
        line->start_s = sqlite3_column_double(stmt, 3);
        line->end_s = sqlite3_column_double(stmt, 4);
    }

    sqlite3_finalize(stmt);
    return i == out->calibration_count ? 0 : -1;
}

static int load_survey_windows(sqlite3 *db, Catalog *out) {
    sqlite3_stmt *stmt = NULL;
    if (count_rows(db, "survey_windows", &out->survey_window_count) != 0) return -1;
    out->survey_windows = calloc(out->survey_window_count, sizeof(*out->survey_windows));
    if (out->survey_window_count && !out->survey_windows) return -1;

    const char *sql =
        "SELECT window_id, start_s, end_s, weight FROM survey_windows ORDER BY window_id";
    if (sqlite3_prepare_v2(db, sql, -1, &stmt, NULL) != SQLITE_OK) return -1;

    size_t i = 0;
    while (sqlite3_step(stmt) == SQLITE_ROW && i < out->survey_window_count) {
        SurveyWindow *win = &out->survey_windows[i++];
        win->window_id = (uint32_t)sqlite3_column_int(stmt, 0);
        win->start_s = sqlite3_column_double(stmt, 1);
        win->end_s = sqlite3_column_double(stmt, 2);
        win->weight = sqlite3_column_double(stmt, 3);
    }

    sqlite3_finalize(stmt);
    return i == out->survey_window_count ? 0 : -1;
}

int load_catalog(const char *path, Catalog *out) {
    sqlite3 *db = NULL;
    memset(out, 0, sizeof(*out));
    if (sqlite3_open_v2(path, &db, SQLITE_OPEN_READONLY, NULL) != SQLITE_OK) return -1;

    int rc = 0;
    if (load_instruments(db, out) != 0) rc = -1;
    if (rc == 0 && load_calibrations(db, out) != 0) rc = -1;
    if (rc == 0 && load_survey_windows(db, out) != 0) rc = -1;
    sqlite3_close(db);

    if (rc != 0) free_catalog(out);
    return rc;
}

const Instrument *find_instrument(const Catalog *catalog, uint32_t instrument_id) {
    for (size_t i = 0; i < catalog->instrument_count; i++) {
        if (catalog->instruments[i].instrument_id == instrument_id) return &catalog->instruments[i];
    }
    return NULL;
}

const SurveyWindow *find_survey_window(const Catalog *catalog, uint32_t window_id) {
    for (size_t i = 0; i < catalog->survey_window_count; i++) {
        if (catalog->survey_windows[i].window_id == window_id) return &catalog->survey_windows[i];
    }
    return NULL;
}

void free_catalog(Catalog *catalog) {
    free(catalog->instruments);
    free(catalog->calibrations);
    free(catalog->survey_windows);
    memset(catalog, 0, sizeof(*catalog));
}
