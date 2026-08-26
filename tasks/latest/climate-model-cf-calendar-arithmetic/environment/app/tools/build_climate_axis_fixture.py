#!/usr/bin/env python3
"""Build-time fixture generator for samples and interrupted climate-axis working state.

Runs only during image build. Not a verifier reference.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import struct
from pathlib import Path

ROOT = Path("/app")
SAMPLES = ROOT / "data" / "samples"
SEGMENTS = ROOT / "data" / "segments"
STATE = Path("/var/lib/climconvert/climate_axis")
CACHE = Path("/var/lib/climconvert/cache")
OUTPUT = Path("/output")

MAGIC = b"CCF1"


def _f64(vals: list[float]) -> bytes:
    return b"".join(struct.pack("<d", v) for v in vals)


def write_ccf(path: Path, header: dict, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    jb = json.dumps(header, separators=(",", ":")).encode()
    with path.open("wb") as fh:
        fh.write(MAGIC)
        fh.write(struct.pack("<I", len(jb)))
        fh.write(jb)
        fh.write(payload)


def write_cft(
    path: Path,
    *,
    calendar: str,
    units: str,
    times: list[float],
    columns: dict[str, list[float]],
    bounds: list[list[float]] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"# calendar={calendar}", f"# units={units}", "# schema_version=1"]
    if bounds is not None:
        lines.append(f"# bounds={json.dumps(bounds)}")
    names = list(columns.keys())
    lines.append("time," + ",".join(names))
    for i, t in enumerate(times):
        row = [str(t)] + [str(columns[n][i]) for n in names]
        lines.append(",".join(row))
    path.write_text("\n".join(lines) + "\n")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_classic_samples() -> None:
    SAMPLES.mkdir(parents=True, exist_ok=True)
    # Gregorian monthly
    times = [0.0, 31.0, 59.0, 90.0]
    temp = [10.0, 11.0, 12.0, 13.0]
    write_ccf(
        SAMPLES / "gregorian_monthly.ccf",
        {
            "schema_version": 1,
            "calendar": "gregorian",
            "units": "days since 2000-01-01 00:00:00",
            "time": times,
            "variables": {
                "temp": {"dtype": "f64", "offset": 0, "count": 4, "agg": "mean"}
            },
        },
        _f64(temp),
    )
    # Proleptic decadal
    times = [0.0, 3652.0, 7305.0]
    temp = [1.0, 2.0, 3.0]
    write_ccf(
        SAMPLES / "proleptic_decadal.ccf",
        {
            "schema_version": 1,
            "calendar": "proleptic_gregorian",
            "units": "days since 1850-01-01 00:00:00",
            "time": times,
            "variables": {
                "temp": {"dtype": "f64", "offset": 0, "count": 3, "agg": "mean"}
            },
        },
        _f64(temp),
    )
    # Bounds interval
    times = [15.0, 45.0, 75.0]
    bounds = [[0.0, 30.0], [30.0, 60.0], [60.0, 90.0]]
    temp = [5.0, 6.0, 7.0]
    write_ccf(
        SAMPLES / "bounds_interval.ccf",
        {
            "schema_version": 1,
            "calendar": "gregorian",
            "units": "days since 2001-01-01 00:00:00",
            "time": times,
            "bounds": bounds,
            "variables": {
                "temp": {"dtype": "f64", "offset": 0, "count": 3, "agg": "mean"}
            },
        },
        _f64(temp),
    )
    # Append base/tail same calendar different origins (360_day)
    write_ccf(
        SAMPLES / "append_base_360day.ccf",
        {
            "schema_version": 1,
            "calendar": "360_day",
            "units": "days since 1900-01-01 00:00:00",
            "time": [0.0, 30.0, 60.0],
            "variables": {
                "temp": {"dtype": "f64", "offset": 0, "count": 3, "agg": "mean"}
            },
        },
        _f64([1.0, 2.0, 3.0]),
    )
    write_ccf(
        SAMPLES / "append_tail_noleap.ccf",
        {
            "schema_version": 1,
            "calendar": "360_day",
            "units": "days since 1900-04-01 00:00:00",
            "time": [0.0, 30.0],
            "variables": {
                "temp": {"dtype": "f64", "offset": 0, "count": 2, "agg": "mean"}
            },
        },
        _f64([4.0, 5.0]),
    )
    # Resample tri-calendar (use gregorian for simplicity after corrected baseline)
    write_ccf(
        SAMPLES / "resample_tricalendar.ccf",
        {
            "schema_version": 1,
            "calendar": "gregorian",
            "units": "days since 2000-01-01 00:00:00",
            "time": [0.0, 10.0, 40.0, 70.0, 100.0],
            "variables": {
                "temp": {"dtype": "f64", "offset": 0, "count": 5, "agg": "mean"},
                "precip": {
                    "dtype": "f64",
                    "offset": 40,
                    "count": 5,
                    "agg": "sum",
                },
            },
        },
        _f64([1, 2, 3, 4, 5]) + _f64([0.1, 0.2, 0.3, 0.4, 0.5]),
    )


def build_climate_axis_fixture() -> None:
    if SEGMENTS.exists():
        shutil.rmtree(SEGMENTS)
    SEGMENTS.mkdir(parents=True)
    if STATE.exists():
        shutil.rmtree(STATE)
    STATE.mkdir(parents=True)
    CACHE.mkdir(parents=True, exist_ok=True)
    OUTPUT.mkdir(parents=True, exist_ok=True)

    # Retired committed-prefix sources (written then deleted; remain in lineage)
    retired_a = SEGMENTS / "_retired_a.ccf"
    retired_b = SEGMENTS / "_retired_b.ccf"
    # Prefix: days 0, 30, 60 in units days since 1900-01-01
    write_ccf(
        retired_a,
        {
            "schema_version": 1,
            "calendar": "360_day",
            "units": "days since 1900-01-01 00:00:00",
            "time": [0.0, 30.0],
            "bounds": [[-15.0, 15.0], [15.0, 45.0]],
            "variables": {
                "temp": {"dtype": "f64", "offset": 0, "count": 2, "agg": "mean"},
                "precip": {"dtype": "f64", "offset": 16, "count": 2, "agg": "sum"},
            },
        },
        _f64([10.0, 11.0]) + _f64([1.0, 1.5]),
    )
    write_ccf(
        retired_b,
        {
            "schema_version": 1,
            "calendar": "360_day",
            "units": "days since 1900-01-01 00:00:00",
            "time": [60.0],
            "bounds": [[45.0, 75.0]],
            "variables": {
                "temp": {"dtype": "f64", "offset": 0, "count": 1, "agg": "mean"},
                "precip": {"dtype": "f64", "offset": 8, "count": 1, "agg": "sum"},
            },
        },
        _f64([12.0]) + _f64([2.0]),
    )

    # Committed archive = merge of retired_a + retired_b
    write_ccf(
        OUTPUT / "archive.ccf",
        {
            "schema_version": 1,
            "calendar": "360_day",
            "units": "days since 1900-01-01 00:00:00",
            "time": [0.0, 30.0, 60.0],
            "bounds": [[-15.0, 15.0], [15.0, 45.0], [45.0, 75.0]],
            "variables": {
                "temp": {"dtype": "f64", "offset": 0, "count": 3, "agg": "mean"},
                "precip": {"dtype": "f64", "offset": 24, "count": 3, "agg": "sum"},
            },
        },
        _f64([10.0, 11.0, 12.0]) + _f64([1.0, 1.5, 2.0]),
    )
    # Monthly rollup seed for the sample generation
    write_ccf(
        OUTPUT / "archive-monthly.ccf",
        {
            "schema_version": 1,
            "calendar": "360_day",
            "units": "days since 1900-01-01 00:00:00",
            "time": [0.0, 30.0, 60.0],
            "variables": {
                "temp": {"dtype": "f64", "offset": 0, "count": 3, "agg": "mean"},
                "precip": {"dtype": "f64", "offset": 24, "count": 3, "agg": "sum"},
            },
        },
        _f64([10.0, 11.0, 12.0]) + _f64([1.0, 1.5, 2.0]),
    )

    dig_a = digest(retired_a)
    dig_b = digest(retired_b)
    n_a, n_b = 2, 1

    # Surviving suffix: overlap at day 60 (identical) + new points
    # Mixed origin: days since 1900-03-01 (= 60 days after 1900-01-01 in 360_day)
    # So encoded 0 in this origin == day 60 in archive units
    suffix_ccf = SEGMENTS / "suffix_overlap.ccf"
    write_ccf(
        suffix_ccf,
        {
            "schema_version": 1,
            "calendar": "360_day",
            "units": "days since 1900-03-01 00:00:00",
            "time": [0.0, 30.0],
            "bounds": [[-15.0, 15.0], [15.0, 45.0]],
            "variables": {
                "temp": {"dtype": "f64", "offset": 0, "count": 2, "agg": "mean"},
                "precip": {"dtype": "f64", "offset": 16, "count": 2, "agg": "sum"},
            },
        },
        # first row identical to archive day-60 row (temp=12, precip=2)
        _f64([12.0, 13.0]) + _f64([2.0, 2.5]),
    )
    suffix_cft = SEGMENTS / "suffix_tail.cft"
    write_cft(
        suffix_cft,
        calendar="360_day",
        units="days since 1900-05-01 00:00:00",
        times=[0.0, 30.0],
        columns={"temp": [14.0, 15.0], "precip": [3.0, 3.5]},
        bounds=[[-15.0, 15.0], [15.0, 45.0]],
    )

    dig_s1 = digest(suffix_ccf)
    dig_s2 = digest(suffix_cft)

    lineage = {
        "records": [
            {
                "path": "/data/segments/_retired_a.ccf",
                "digest": dig_a,
                "retired": True,
                "observation_count": n_a,
            },
            {
                "path": "/data/segments/_retired_b.ccf",
                "digest": dig_b,
                "retired": True,
                "observation_count": n_b,
            },
        ]
    }
    (STATE / "lineage.json").write_text(json.dumps(lineage, indent=2, sort_keys=True) + "\n")

    # Checkpoint records the committed generation and retired prefix paths.
    checkpoint = {
        "committed_generation_id": "gen1",
        "planned_generation_id": "gen2-staged",
        "completed_source_paths": ["/data/segments/_retired_a.ccf", "/data/segments/_retired_b.ccf"],
        "archive_path": "/output/archive.ccf",
        "rollup_path": "/output/archive-monthly.ccf",
        "report_path": "/output/climate-axis-report.json",
    }
    (STATE / "checkpoint.json").write_text(
        json.dumps(checkpoint, indent=2, sort_keys=True) + "\n"
    )

    # Journal: incomplete staged generation
    journal = [
        {"event": "stage_ready", "generation_id": "gen2-staged", "detail": "partial"},
        {
            "event": "checkpoint_advanced",
            "generation_id": "gen2-staged",
            "detail": "before_publish",
        },
    ]
    (STATE / "journal.jsonl").write_text(
        "".join(json.dumps(e, sort_keys=True) + "\n" for e in journal)
    )

    # Staged archive fragment left from the interrupted attempt
    stage = STATE / "stage"
    stage.mkdir(parents=True, exist_ok=True)
    write_ccf(
        stage / "archive.ccf",
        {
            "schema_version": 1,
            "calendar": "360_day",
            "units": "days since 1900-01-01 00:00:00",
            "time": [60.0, 90.0],
            "variables": {
                "temp": {"dtype": "f64", "offset": 0, "count": 2, "agg": "mean"},
                "precip": {"dtype": "f64", "offset": 16, "count": 2, "agg": "sum"},
            },
        },
        _f64([12.0, 13.0]) + _f64([2.0, 2.5]),
    )

    # Prior report left from the interrupted attempt
    stale_report = {
        "report_format_version": 1,
        "committed_generation_id": "gen2-staged",
        "run_id": "sample",
        "archive_path": "/output/archive.ccf",
        "archive_digest": "0" * 64,
        "rollup_path": "/output/archive-monthly.ccf",
        "rollup_digest": "1" * 64,
        "observation_count": 2,
        "first_instant": [1900, 3, 1],
        "last_instant": [1900, 4, 1],
        "recovery_outcome": "interrupted",
        "conflict": False,
        "source_lineage": lineage["records"],
        "planned_remaining": ["/data/segments/suffix_overlap.ccf", "/data/segments/suffix_tail.cft"],
    }
    (OUTPUT / "climate-axis-report.json").write_text(
        json.dumps(stale_report, indent=2, sort_keys=True) + "\n"
    )

    # Pre-existing monthly cache entry for the sample
    stale_key = hashlib.sha256(
        b"/output/archive.ccf" + b"0" + b"5184000" + b"360_day"
    ).hexdigest()
    write_ccf(
        CACHE / f"{stale_key}.ccf",
        {
            "schema_version": 1,
            "calendar": "360_day",
            "units": "days since 1900-01-01 00:00:00",
            "time": [999.0],
            "variables": {
                "temp": {"dtype": "f64", "offset": 0, "count": 1, "agg": "mean"},
                "precip": {"dtype": "f64", "offset": 8, "count": 1, "agg": "sum"},
            },
        },
        _f64([99.0]) + _f64([99.0]),
    )

    # Manifest
    manifest = f'''schema_version = 1
calendar = "360_day"
units = "days since 1900-01-01 00:00:00"
state_dir = "/var/lib/climconvert/climate_axis"
archive_path = "/output/archive.ccf"
rollup_path = "/output/archive-monthly.ccf"
report_path = "/output/climate-axis-report.json"
run_id = "sample"
cache_dir = "/var/lib/climconvert/cache"

[[sources]]
path = "/data/segments/_retired_a.ccf"
role = "committed"
digest = "{dig_a}"

[[sources]]
path = "/data/segments/_retired_b.ccf"
role = "committed"
digest = "{dig_b}"

[[sources]]
path = "/data/segments/suffix_overlap.ccf"
role = "segment"
digest = "{dig_s1}"

[[sources]]
path = "/data/segments/suffix_tail.cft"
role = "segment"
digest = "{dig_s2}"
'''
    (ROOT / "data" / "climate-axis-manifest.toml").write_text(manifest)

    # Retire historical sources
    retired_a.unlink()
    retired_b.unlink()

    # Symlink convenience: /data -> /app/data when present
    data_root = Path("/data")
    if not data_root.exists():
        try:
            data_root.symlink_to(ROOT / "data")
        except OSError:
            data_root.mkdir(parents=True, exist_ok=True)

    print("Built classic samples and interrupted climate-axis fixture")


if __name__ == "__main__":
    build_classic_samples()
    build_climate_axis_fixture()
