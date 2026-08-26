"""Checks for Cedar Fork Muskingum channel routing quantities."""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import authority

BIN = os.environ.get("FLOOD_BIN", "/app/bin/channel-route")
SURVEY = os.environ.get("FLOOD_SURVEY", "/app/data/survey.bin")
CAL = os.environ.get("FLOOD_CAL", "/app/calibration")
SCHEMA = os.environ.get("FLOOD_SCHEMA", "/app/config/channel_quantities.schema.json")
FIXTURES = Path(os.environ.get("FLOOD_FIXTURES", "/tests/fixtures"))


def _run(survey_path: str) -> dict:
    proc = subprocess.run([BIN, survey_path], capture_output=True, check=True)
    return json.loads(proc.stdout.decode("utf-8"))


def test_channel_route_is_ruby():
    """The Cedar Fork field calculator at /app/bin/channel-route must be an executable Ruby program."""
    assert os.path.isfile(BIN)
    assert os.access(BIN, os.X_OK)
    with open(BIN, "rb") as fh:
        head = fh.read(128)
    assert head.startswith(b"#!") or b"ruby" in head.lower()
    assert head[:4] != b"\x7fELF"


def test_desk_events_match_authority():
    """Desk survey events under /app/data must match the independent authority."""
    got = _run(SURVEY)
    want = authority.analyze_survey(SURVEY)
    assert got == want
    assert os.path.isfile(SCHEMA)


def test_calibration_cases_match_authority():
    """Every shipped calibration case must match its measured target quantities."""
    cal_root = Path(CAL)
    for case_dir in sorted(p for p in cal_root.iterdir() if p.is_dir()):
        survey = case_dir / "survey.bin"
        target = json.load(open(case_dir / "calibration.json", encoding="utf-8"))
        got = _run(str(survey))
        assert list(got.keys()) == ["event"]
        assert got["event"] == target
        assert got["event"] == authority.analyze_first_event(survey)


def test_holdout_basins_match_authority():
    """Held-out survey fixtures must match the authority with no shipped answers."""
    for hid in sorted(p.name for p in FIXTURES.iterdir() if p.is_dir()):
        survey = FIXTURES / hid / "survey.bin"
        got = _run(str(survey))
        want = {hid: authority.analyze_first_event(survey)}
        assert got == want
