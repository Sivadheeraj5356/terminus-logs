"""Behavioral verifier for the vacuum-interrupter reconstruction CLI."""

from __future__ import annotations

import json
import math
import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

from interrupter_reference import reconstruct


APP = Path("/app")
SOURCE = APP / "src" / "main.cpp"
BINARY = APP / "arcguard"
BUILD_DIRECTORY = Path("/tmp/arcguard-build")
BUILD_SOURCE = BUILD_DIRECTORY / "src" / "main.cpp"
BUILD_BINARY = BUILD_DIRECTORY / "arcguard"
NO_SPAWN_SOURCE = Path("/tests/no_spawn.c")
NO_SPAWN_LIBRARY = Path("/tmp/arcguard_no_spawn.so")
RUNNER_UID = 10001
RUNNER_GID = 10001
TOLERANCE = 1e-7
VALID_STATES = {"normal", "restrike", "conditioning", "welded"}


def drop_runner_privileges() -> None:
    """Enter the dedicated, unprivileged account used for compilation and execution."""

    os.setgroups([])
    os.setgid(RUNNER_GID)
    os.setuid(RUNNER_UID)


def configuration(**changes: float) -> dict:
    """Return a physically valid baseline configuration with optional changes."""

    values = {
        "window_start": 0.0,
        "window_end": 40.0,
        "strike_level": 5.0,
        "clear_level": 2.5,
        "current_weight": 0.08,
        "pressure_weight": 0.12,
        "gap_weight": 0.5,
        "current_slope": 0.12,
        "pressure_slope": 0.03,
        "gap_slope": 0.01,
        "conditioning_relief": 1.4,
        "qualify_sec": 2.0,
        "erosion_limit": 36.0,
        "start_current": 5.0,
        "start_pressure": 2.5,
        "start_gap": 1.0,
    }
    values.update(changes)
    return values


def encode_stream(config: dict, events: list[dict]) -> str:
    """Encode the public newline-delimited JSON protocol."""

    records = [config, *events]
    return "\n".join(json.dumps(record, separators=(",", ":")) for record in records) + "\n"


def run_program(config: dict, events: list[dict]) -> list[dict]:
    """Execute the submitted binary and decode its single JSON result."""

    completed = subprocess.run(
        [str(BINARY)],
        input=encode_stream(config, events),
        text=True,
        capture_output=True,
        timeout=8,
        check=False,
        cwd=BUILD_DIRECTORY,
        env={
            "PATH": "/usr/bin:/bin",
            "LANG": "C",
            "LC_ALL": "C",
            "LD_PRELOAD": str(NO_SPAWN_LIBRARY),
        },
        preexec_fn=drop_runner_privileges,
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stderr == ""
    lines = [line for line in completed.stdout.splitlines() if line.strip()]
    assert len(lines) == 1, completed.stdout
    result = json.loads(lines[0])
    assert isinstance(result, list)
    return result


def check_canonical(spans: list[dict], config: dict) -> None:
    """Check schema, exact coverage, ordering, and canonical merging."""

    assert spans
    expected_start = float(config["window_start"])
    assert math.isclose(float(spans[0]["start"]), expected_start, abs_tol=TOLERANCE)
    for index, span in enumerate(spans):
        assert set(span) == {"state", "start", "end"}
        assert span["state"] in VALID_STATES
        assert isinstance(span["start"], (int, float)) and not isinstance(span["start"], bool)
        assert isinstance(span["end"], (int, float)) and not isinstance(span["end"], bool)
        assert math.isfinite(float(span["start"])) and math.isfinite(float(span["end"]))
        assert float(span["end"]) - float(span["start"]) > 1e-9
        assert math.isclose(float(span["start"]), expected_start, abs_tol=TOLERANCE)
        expected_start = float(span["end"])
        if index:
            assert spans[index - 1]["state"] != span["state"]
    assert math.isclose(expected_start, float(config["window_end"]), abs_tol=TOLERANCE)


def compare_reference(config: dict, events: list[dict]) -> list[dict]:
    """Compare all visible states and numerical boundaries to the independent model."""

    actual = run_program(config, events)
    expected = reconstruct(config, events)
    check_canonical(actual, config)
    assert len(actual) == len(expected), (actual, expected)
    for got, want in zip(actual, expected):
        assert got["state"] == want["state"]
        assert math.isclose(float(got["start"]), float(want["start"]), abs_tol=TOLERANCE)
        assert math.isclose(float(got["end"]), float(want["end"]), abs_tol=TOLERANCE)
    return actual


@pytest.fixture(scope="session", autouse=True)
def build_submission() -> None:
    """Compile one regular source copy with fixed flags into a native ELF."""

    source_status = SOURCE.lstat()
    assert stat.S_ISREG(source_status.st_mode), "submission source must be a regular file"
    assert NO_SPAWN_SOURCE.is_file()
    guard_build = subprocess.run(
        [
            "cc",
            "-shared",
            "-fPIC",
            "-O2",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-o",
            str(NO_SPAWN_LIBRARY),
            str(NO_SPAWN_SOURCE),
        ],
        text=True,
        capture_output=True,
        timeout=20,
        check=False,
    )
    assert guard_build.returncode == 0, guard_build.stdout + guard_build.stderr
    shutil.rmtree(BUILD_DIRECTORY, ignore_errors=True)
    BUILD_DIRECTORY.mkdir(mode=0o700)
    BUILD_SOURCE.parent.mkdir()
    shutil.copyfile(SOURCE, BUILD_SOURCE)
    shutil.copyfile(APP / "Makefile", BUILD_DIRECTORY / "Makefile")
    os.chown(BUILD_DIRECTORY, RUNNER_UID, RUNNER_GID)
    os.chown(BUILD_SOURCE.parent, RUNNER_UID, RUNNER_GID)
    os.chown(BUILD_SOURCE, RUNNER_UID, RUNNER_GID)
    BUILD_SOURCE.chmod(0o400)

    completed = subprocess.run(
        [
            "/usr/bin/make",
            "--always-make",
            "arcguard",
        ],
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
        cwd=BUILD_DIRECTORY,
        env={"PATH": "/usr/local/bin:/usr/bin:/bin", "LANG": "C", "LC_ALL": "C"},
        preexec_fn=drop_runner_privileges,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    binary_status = BUILD_BINARY.lstat()
    assert stat.S_ISREG(binary_status.st_mode), "compiler output must be a regular file"
    with BUILD_BINARY.open("rb") as executable:
        assert executable.read(4) == b"\x7fELF", "compiler output must be a native ELF"

    # The runner may mount /app separately from /tmp, so an atomic rename can
    # fail with EXDEV even though both paths are otherwise valid. Copy the
    # already verified native ELF across filesystems, then lock its ownership
    # and mode before any test executes it.
    shutil.copyfile(BUILD_BINARY, BINARY)
    os.chown(BINARY, 0, 0)
    BINARY.chmod(0o555)


def test_quadratic_stress_crosses_both_thresholds() -> None:
    """A curved stress trace must enter, clear, and later re-enter hysteresis regions."""

    config = configuration(
        window_end=24.0,
        current_weight=0.22,
        pressure_weight=0.0,
        gap_weight=0.0,
        current_slope=0.7,
        pressure_slope=0.0,
        gap_slope=0.0,
        start_current=-7.0,
        start_pressure=0.0,
        start_gap=0.0,
        qualify_sec=0.8,
        erosion_limit=500.0,
    )
    spans = compare_reference(config, [])
    assert {span["state"] for span in spans} >= {"normal", "restrike"}
    assert sum(span["state"] == "restrike" for span in spans) == 2


def test_qualification_resets_before_completion() -> None:
    """A sub-strike sample must discard unfinished qualification rather than pause it."""

    config = configuration(
        window_end=15.0,
        current_weight=1.0,
        pressure_weight=0.0,
        gap_weight=0.0,
        current_slope=0.0,
        pressure_slope=0.0,
        gap_slope=0.0,
        start_current=3.0,
        strike_level=8.0,
        clear_level=2.0,
        qualify_sec=4.0,
        erosion_limit=1000.0,
    )
    events = [
        {"t": 2.5, "kind": "current_sample", "value": 1.0},
        {"t": 4.0, "kind": "current_sample", "value": 3.0},
    ]
    spans = compare_reference(config, events)
    restrike = next(span for span in spans if span["state"] == "restrike")
    assert math.isclose(float(restrike["start"]), 8.0, abs_tol=TOLERANCE)


def test_restrike_uses_clear_level_hysteresis() -> None:
    """A qualified restrike must survive inside the band and clear only at the lower level."""

    config = configuration(
        window_end=18.0,
        current_weight=1.0,
        pressure_weight=0.0,
        gap_weight=0.0,
        current_slope=0.0,
        pressure_slope=0.0,
        gap_slope=0.0,
        start_current=3.0,
        strike_level=8.0,
        clear_level=3.0,
        qualify_sec=1.0,
        erosion_limit=1000.0,
    )
    events = [
        {"t": 4.0, "kind": "current_sample", "value": 2.0},
        {"t": 9.0, "kind": "current_sample", "value": 1.5},
        {"t": 12.0, "kind": "current_sample", "value": 3.0},
    ]
    spans = compare_reference(config, events)
    assert any(
        span["state"] == "restrike" and float(span["start"]) <= 4.0 and float(span["end"]) >= 9.0
        for span in spans
    )


def test_erosion_persists_across_cleared_episodes() -> None:
    """Separated restrikes must share the persistent erosion ledger and eventually weld."""

    config = configuration(
        window_end=20.0,
        current_weight=1.0,
        pressure_weight=0.0,
        gap_weight=0.0,
        current_slope=0.0,
        pressure_slope=0.0,
        gap_slope=0.0,
        start_current=3.0,
        strike_level=8.0,
        clear_level=2.0,
        qualify_sec=0.0,
        erosion_limit=35.0,
    )
    events = [
        {"t": 3.0, "kind": "current_sample", "value": 1.0},
        {"t": 8.0, "kind": "current_sample", "value": 3.0},
    ]
    spans = compare_reference(config, events)
    welded = next(span for span in spans if span["state"] == "welded")
    assert 8.0 < float(welded["start"]) < 20.0


def test_conditioning_changes_stress_but_not_hidden_clocks() -> None:
    """Conditioning must mask the display, relieve stress, and retain hidden evolution."""

    config = configuration(
        window_end=18.0,
        current_weight=1.0,
        pressure_weight=0.0,
        gap_weight=0.0,
        current_slope=0.25,
        pressure_slope=0.0,
        gap_slope=0.0,
        start_current=2.8,
        strike_level=8.0,
        clear_level=4.0,
        conditioning_relief=1.0,
        qualify_sec=1.5,
        erosion_limit=30.0,
    )
    events = [
        {"t": 1.0, "kind": "conditioning_on"},
        {"t": 9.0, "kind": "conditioning_off"},
        {"t": 12.0, "kind": "conditioning_on"},
    ]
    spans = compare_reference(config, events)
    assert any(span["state"] == "conditioning" for span in spans)
    assert spans[-1]["state"] == "welded"


def test_all_three_signals_drift_and_reset_independently() -> None:
    """Current, pressure, and gap reports must reset only their matching trajectories."""

    config = configuration(window_end=35.0, erosion_limit=90.0)
    events = [
        {"t": 5.0, "kind": "pressure_sample", "value": 4.5},
        {"t": 10.0, "kind": "gap_sample", "value": 2.4},
        {"t": 14.0, "kind": "current_sample", "value": 8.0},
        {"t": 22.0, "kind": "pressure_sample", "value": 1.2},
        {"t": 26.0, "kind": "gap_sample", "value": 0.3},
    ]
    compare_reference(config, events)


def test_near_equal_batch_keeps_input_line_order() -> None:
    """Near-equal events must form one batch whose final values follow original line order."""

    config = configuration(
        window_end=14.0,
        current_slope=0.0,
        pressure_slope=0.0,
        gap_slope=0.0,
        qualify_sec=0.0,
        erosion_limit=500.0,
    )
    events = [
        {"t": 4.0 + 8e-10, "kind": "current_sample", "value": 10.0},
        {"t": 4.0, "kind": "current_sample", "value": 1.0},
        {"t": 4.0 + 3e-10, "kind": "gap_sample", "value": 0.2},
        {"t": 8.0, "kind": "conditioning_on"},
        {"t": 8.0 + 5e-10, "kind": "conditioning_off"},
    ]
    actual = compare_reference(config, events)
    timestamp_ordered = sorted(events, key=lambda event: event["t"])
    assert actual != reconstruct(config, timestamp_ordered)


def test_weld_at_horizon_has_no_empty_tail() -> None:
    """A weld boundary exactly at the window end must not create a zero-length span."""

    config = configuration(
        window_end=6.0,
        current_weight=1.0,
        pressure_weight=0.0,
        gap_weight=0.0,
        current_slope=0.0,
        pressure_slope=0.0,
        gap_slope=0.0,
        start_current=3.0,
        strike_level=8.0,
        clear_level=3.0,
        qualify_sec=1.0,
        erosion_limit=30.0,
    )
    spans = compare_reference(config, [])
    assert spans[-1]["state"] == "restrike"
    assert math.isclose(float(spans[-1]["end"]), 6.0, abs_tol=TOLERANCE)


def test_clear_level_tangent_clears_restrike() -> None:
    """A quadratic minimum that only touches clear_level must still clear restrike."""

    config = configuration(
        window_end=5.0,
        current_weight=1.0,
        pressure_weight=0.0,
        gap_weight=1.0,
        current_slope=1.0,
        pressure_slope=0.0,
        gap_slope=0.0,
        start_current=-2.5,
        start_pressure=0.0,
        start_gap=-2.0,
        strike_level=6.0,
        clear_level=2.0,
        qualify_sec=0.0,
        erosion_limit=1000.0,
    )
    spans = compare_reference(config, [])
    assert any(
        span["state"] == "normal"
        and math.isclose(float(span["start"]), 2.5, abs_tol=TOLERANCE)
        and math.isclose(float(span["end"]), 4.5, abs_tol=TOLERANCE)
        for span in spans
    )


def test_zero_qualification_strike_tangent_enters_restrike() -> None:
    """With zero qualification, touching strike_level at one instant must latch restrike."""

    config = configuration(
        window_end=5.0,
        current_weight=-1.0,
        pressure_weight=0.0,
        gap_weight=1.0,
        current_slope=1.0,
        pressure_slope=0.0,
        gap_slope=0.0,
        start_current=-2.0,
        start_pressure=0.0,
        start_gap=-5.0,
        strike_level=5.0,
        clear_level=1.0,
        qualify_sec=0.0,
        erosion_limit=1000.0,
    )
    spans = compare_reference(config, [])
    restrike = next(span for span in spans if span["state"] == "restrike")
    assert math.isclose(float(restrike["start"]), 2.0, abs_tol=TOLERANCE)
    assert math.isclose(float(restrike["end"]), 4.0, abs_tol=TOLERANCE)


@pytest.mark.parametrize("profile", range(24))
def test_generated_compatibility_matrix(profile: int) -> None:
    """Compatible coefficient, slope, event, hysteresis, and masking variants must generalize."""

    config = configuration(
        window_start=1.5 + 0.1 * (profile % 3),
        window_end=52.0 + (profile % 5),
        strike_level=4.6 + 0.18 * (profile % 4),
        clear_level=2.0 + 0.14 * (profile % 5),
        current_weight=0.045 + 0.009 * (profile % 6),
        pressure_weight=0.07 + 0.013 * ((profile * 3) % 5),
        gap_weight=0.28 + 0.07 * ((profile * 5) % 4),
        current_slope=-0.11 + 0.045 * (profile % 6),
        pressure_slope=-0.045 + 0.021 * ((profile * 2) % 5),
        gap_slope=-0.018 + 0.012 * ((profile * 4) % 5),
        conditioning_relief=0.7 + 0.19 * (profile % 6),
        qualify_sec=0.0 if profile % 7 == 0 else 0.8 + 0.45 * (profile % 5),
        erosion_limit=18.0 + 4.5 * (profile % 7),
        start_current=5.5 + 0.5 * (profile % 5),
        start_pressure=2.0 + 0.35 * ((profile * 2) % 6),
        start_gap=0.7 + 0.23 * ((profile * 3) % 5),
    )
    base = float(config["window_start"])
    events = [
        {"t": base + 5.0, "kind": "conditioning_on"},
        {"t": base + 8.0 + 2e-10, "kind": "pressure_sample", "value": 1.4 + 0.2 * (profile % 4)},
        {"t": base + 8.0, "kind": "current_sample", "value": 4.0 + 0.55 * (profile % 6)},
        {"t": base + 13.0, "kind": "gap_sample", "value": 0.5 + 0.16 * (profile % 7)},
        {"t": base + 17.0, "kind": "conditioning_off"},
        {"t": base + 23.0, "kind": "current_sample", "value": 7.0 - 0.3 * (profile % 5)},
        {"t": base + 29.0, "kind": "pressure_sample", "value": 3.8 - 0.18 * (profile % 6)},
        {"t": base + 34.0, "kind": "conditioning_on"},
        {"t": base + 41.0, "kind": "conditioning_off"},
    ]
    compare_reference(config, events)
