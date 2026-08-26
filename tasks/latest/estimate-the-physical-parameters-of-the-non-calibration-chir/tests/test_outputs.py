"""Tests for recover-aliased-spectral-events."""

import json
import math
import os
import shutil
import sqlite3
import subprocess

APP = "/app"
JSON_PATH = "/app/output/events.json"
SQLITE_PATH = "/app/output/recovered.sqlite"

EXPECTED = [
    {"f0_hz": 6125.25, "chirp_hz_per_s": 0.50, "start_s": 0.72, "end_s": 3.24},
    {"f0_hz": 18432.75, "chirp_hz_per_s": -4.25, "start_s": 0.22, "end_s": 2.70},
    {"f0_hz": 32781.40, "chirp_hz_per_s": 6.80, "start_s": 1.02, "end_s": 3.76},
]

START_TOLERANCE_S = 0.42
END_TOLERANCE_S = 0.28

CALIBRATIONS = [
    {"f0_hz": 7342.00, "chirp_hz_per_s": 0.00},
    {"f0_hz": 15120.00, "chirp_hz_per_s": -1.25},
]

PROMOTED_CALIBRATION = {"label": "promoted-6k", "f0_hz": 6125.25, "chirp_hz_per_s": 0.50}


def _run_recover():
    subprocess.run(["make", "clean", "all"], cwd=APP, check=True, capture_output=True, text=True)
    os.makedirs("/app/output", exist_ok=True)
    subprocess.run(["/app/bin/recover"], cwd=APP, check=True, capture_output=True, text=True)


def _load_events():
    if not os.path.exists(JSON_PATH):
        _run_recover()
    with open(JSON_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return data["events"]


def _nearest(expected, events):
    return min(events, key=lambda e: abs(float(e["f0_hz"]) - expected["f0_hz"]))


def _load_json_events(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)["events"]


def _remove_outputs():
    if os.path.exists(JSON_PATH):
        os.remove(JSON_PATH)
    if os.path.exists(SQLITE_PATH):
        os.remove(SQLITE_PATH)


def _run_existing_recover():
    _remove_outputs()
    subprocess.run(["/app/bin/recover"], cwd=APP, check=True, capture_output=True, text=True)
    return _load_json_events(JSON_PATH)


def test_recovery_outputs_are_created():
    """The recovery executable writes both required output files."""
    _run_recover()
    assert os.path.isfile(JSON_PATH)
    assert os.path.isfile(SQLITE_PATH)


def test_json_fields_and_source_count():
    """The JSON output contains exactly the physical source estimates."""
    events = _load_events()
    assert len(events) == len(EXPECTED)
    for event in events:
        assert isinstance(event["event_id"], str) and event["event_id"]
        assert float(event["f0_hz"]) > 0
        assert -20.0 <= float(event["chirp_hz_per_s"]) <= 20.0
        assert 0.0 <= float(event["start_s"]) < float(event["end_s"]) <= 4.2
        assert float(event["relative_power"]) > 0
        assert int(event["support"]) >= 4


def test_recovered_frequencies_and_chirps_match_physical_events():
    """Recovered frequencies and chirps match the hidden physical sources."""
    events = _load_events()
    for expected in EXPECTED:
        event = _nearest(expected, events)
        assert math.isclose(float(event["f0_hz"]), expected["f0_hz"], abs_tol=8.0)
        assert math.isclose(float(event["chirp_hz_per_s"]), expected["chirp_hz_per_s"], abs_tol=1.4)


def test_recovered_activity_windows_are_consistent():
    """Recovered start and end times describe the physical source intervals."""
    events = _load_events()
    for expected in EXPECTED:
        event = _nearest(expected, events)
        assert math.isclose(float(event["start_s"]), expected["start_s"], abs_tol=START_TOLERANCE_S)
        assert math.isclose(float(event["end_s"]), expected["end_s"], abs_tol=END_TOLERANCE_S)


def test_calibration_lines_are_not_reported_as_events():
    """Known calibration tones are excluded from the physical source estimates."""
    events = _load_events()
    assert len(events) == len(EXPECTED)
    for event in events:
        for cal in CALIBRATIONS:
            same_freq = math.isclose(float(event["f0_hz"]), cal["f0_hz"], abs_tol=8.0)
            same_chirp = math.isclose(float(event["chirp_hz_per_s"]), cal["chirp_hz_per_s"], abs_tol=1.0)
            assert not (same_freq and same_chirp)


def test_sqlite_output_matches_json_estimates():
    """The recovered SQLite table mirrors the JSON source estimates."""
    events = _load_events()
    assert os.path.isfile(SQLITE_PATH)
    conn = sqlite3.connect(SQLITE_PATH)
    try:
        rows = conn.execute(
            "SELECT event_id, f0_hz, chirp_hz_per_s, start_s, end_s, relative_power, support "
            "FROM events ORDER BY f0_hz"
        ).fetchall()
    finally:
        conn.close()

    json_rows = sorted(events, key=lambda e: float(e["f0_hz"]))
    assert len(rows) == len(EXPECTED)
    assert len(rows) == len(json_rows)
    for row, event in zip(rows, json_rows):
        assert row[0] == event["event_id"]
        assert math.isclose(row[1], float(event["f0_hz"]), abs_tol=1e-6)
        assert math.isclose(row[2], float(event["chirp_hz_per_s"]), abs_tol=1e-6)
        assert math.isclose(row[3], float(event["start_s"]), abs_tol=1e-6)
        assert math.isclose(row[4], float(event["end_s"]), abs_tol=1e-6)
        assert math.isclose(row[5], float(event["relative_power"]), rel_tol=1e-6)
        assert row[6] == int(event["support"])


def test_recovery_uses_input_catalog_and_observations(tmp_path):
    """The recovery executable honors calibration metadata from the current catalog."""
    subprocess.run(["make", "clean", "all"], cwd=APP, check=True, capture_output=True, text=True)
    catalog_backup = tmp_path / "catalog.sqlite.bak"
    shutil.copy("/app/catalog.sqlite", catalog_backup)

    try:
        conn = sqlite3.connect("/app/catalog.sqlite")
        try:
            conn.execute(
                "INSERT INTO calibration_lines(label, f0_hz, chirp_hz_per_s, start_s, end_s) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    PROMOTED_CALIBRATION["label"],
                    PROMOTED_CALIBRATION["f0_hz"],
                    PROMOTED_CALIBRATION["chirp_hz_per_s"],
                    0.0,
                    4.2,
                ),
            )
            conn.commit()
        finally:
            conn.close()

        events = _run_existing_recover()
        for event in events:
            same_freq = math.isclose(float(event["f0_hz"]), PROMOTED_CALIBRATION["f0_hz"], abs_tol=8.0)
            same_chirp = math.isclose(
                float(event["chirp_hz_per_s"]), PROMOTED_CALIBRATION["chirp_hz_per_s"], abs_tol=1.0
            )
            assert not (same_freq and same_chirp)

        for expected in EXPECTED[1:]:
            event = _nearest(expected, events)
            assert math.isclose(float(event["f0_hz"]), expected["f0_hz"], abs_tol=12.0)

        conn = sqlite3.connect(SQLITE_PATH)
        try:
            row_count = conn.execute("SELECT count(*) FROM events").fetchone()[0]
        finally:
            conn.close()
        assert row_count == len(events)
    finally:
        shutil.copy(catalog_backup, "/app/catalog.sqlite")


def test_recovery_responds_to_observation_changes(tmp_path):
    """The recovery executable derives support or power from the current observations."""
    subprocess.run(["make", "clean", "all"], cwd=APP, check=True, capture_output=True, text=True)
    removed_bundle = "/app/observations/vel_412.ase"
    bundle_backup = tmp_path / "vel_412.ase"
    shutil.copy(removed_bundle, bundle_backup)

    try:
        baseline = _run_existing_recover()
        os.remove(removed_bundle)
        reduced = _run_existing_recover()

        baseline_support = sum(int(event["support"]) for event in baseline)
        reduced_support = sum(int(event["support"]) for event in reduced)
        baseline_power = sum(float(event["relative_power"]) for event in baseline)
        reduced_power = sum(float(event["relative_power"]) for event in reduced)

        assert reduced_support < baseline_support or not math.isclose(
            reduced_power, baseline_power, rel_tol=0.05
        )
    finally:
        shutil.copy(bundle_backup, removed_bundle)
