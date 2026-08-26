"""Verifier for climate archive compaction recovery."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import struct
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Tuple

import pytest


@dataclass(frozen=True)
class UnitsOrigin:
    year: int
    month: int
    day: int
    echo: str

    @classmethod
    def parse(cls, units: str) -> "UnitsOrigin":
        parts = units.strip().split()
        if len(parts) < 4 or parts[0] != "days" or parts[1] != "since":
            raise ValueError(f"invalid units: {units}")
        date_part = parts[2]
        y, m, d = [int(x) for x in date_part.split("-")]
        return cls(y, m, d, units.strip())


def _days_in_month(calendar: str, year: int, month: int) -> int:
    if calendar == "360_day":
        return 30
    if calendar == "noleap":
        if month == 2:
            return 28
        if month in (1, 3, 5, 7, 8, 10, 12):
            return 31
        return 30
    if month == 2:
        leap = (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0)
        return 29 if leap else 28
    if month in (1, 3, 5, 7, 8, 10, 12):
        return 31
    return 30


def days_from_origin_to_ymd(
    calendar: str, origin: UnitsOrigin, encoded: float
) -> Tuple[int, int, int]:
    whole = int(encoded // 1)
    year, month, day = origin.year, origin.month, origin.day
    remaining = whole
    while remaining > 0:
        dim = _days_in_month(calendar, year, month)
        left = dim - day + 1
        if remaining < left:
            day += remaining
            remaining = 0
        else:
            remaining -= left
            day = 1
            if month == 12:
                month, year = 1, year + 1
            else:
                month += 1
    return year, month, day


def write_ccf(path: Path, header: dict, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    json_bytes = json.dumps(header, separators=(",", ":")).encode("utf-8")
    with path.open("wb") as fh:
        fh.write(b"CCF1")
        fh.write(struct.pack("<I", len(json_bytes)))
        fh.write(json_bytes)
        fh.write(payload)


def f64_bytes(values: list[float]) -> bytes:
    return b"".join(struct.pack("<d", v) for v in values)


def build_axis_file(
    path: Path,
    *,
    calendar: str,
    units: str,
    times: list[float],
    temp: list[float],
    seed_tag: str,
) -> None:
    n = len(times)
    header = {
        "schema_version": 1,
        "calendar": calendar,
        "units": units,
        "time": times,
        "variables": {
            "temp": {"dtype": "f64", "offset": 0, "count": n, "agg": "mean"},
        },
        "seed_tag": seed_tag,
    }
    write_ccf(path, header, f64_bytes(temp))


BIN = Path("/app/bin/climconvert")
SAMPLES = Path("/data/samples")
SEGMENTS = Path("/data/segments")
MANIFEST = Path("/app/data/climate-axis-manifest.toml")
STATE = Path("/var/lib/climconvert/climate_axis")
ARCHIVE = Path("/output/archive.ccf")
ROLLUP = Path("/output/archive-monthly.ccf")
REPORT = Path("/output/climate-axis-report.json")
REPORT_FORMAT_VERSION = 1


def _run(cmd: list[str], *, check: bool = True, env_extra: dict | None = None) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["TZ"] = "UTC"
    env["PATH"] = "/app/bin:" + env.get("PATH", "/usr/bin:/bin")
    if env_extra:
        env.update(env_extra)
    proc = subprocess.run(cmd, check=False, capture_output=True, text=True, env=env)
    if check and proc.returncode != 0:
        raise AssertionError(
            f"command failed ({proc.returncode}): {' '.join(cmd)}\n"
            f"stdout={proc.stdout}\nstderr={proc.stderr}"
        )
    return proc


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_ccf(path: Path) -> tuple[dict, bytes]:
    data = path.read_bytes()
    assert data[:4] == b"CCF1"
    (json_len,) = struct.unpack_from("<I", data, 4)
    header = json.loads(data[8 : 8 + json_len].decode("utf-8"))
    payload = data[8 + json_len :]
    return header, payload


def _read_f64_column(payload: bytes, offset: int, count: int) -> list[float]:
    out: list[float] = []
    for i in range(count):
        (val,) = struct.unpack_from("<d", payload, offset + i * 8)
        out.append(val)
    return out


def _assert_header_payload_alignment(header: dict, payload: bytes) -> None:
    n = len(header["time"])
    assert n >= 1
    variables = header["variables"]
    assert variables
    for name, meta in variables.items():
        assert meta["count"] == n
        assert meta["dtype"] == "f64"
        col = _read_f64_column(payload, meta["offset"], meta["count"])
        assert len(col) == n
    if "bounds" in header and header["bounds"] is not None:
        assert len(header["bounds"]) == n
        for pair in header["bounds"]:
            assert len(pair) == 2
            assert pair[0] <= pair[1]


@pytest.fixture(scope="session", autouse=True)
def _session_environment() -> None:
    assert BIN.exists(), f"missing CLI: {BIN}"
    proc = _run([str(BIN), "--help"], check=False)
    assert proc.returncode == 0, proc.stderr


def _read_ccf_header(path: Path) -> dict:
    return _read_ccf(path)[0]


def _snapshot_outputs() -> dict[str, bytes | None]:
    return {
        "archive": ARCHIVE.read_bytes() if ARCHIVE.exists() else None,
        "rollup": ROLLUP.read_bytes() if ROLLUP.exists() else None,
        "report": REPORT.read_bytes() if REPORT.exists() else None,
        "checkpoint": (STATE / "checkpoint.json").read_bytes()
        if (STATE / "checkpoint.json").exists()
        else None,
    }


def test_resume_retired_prefix_includes_history_and_suffix() -> None:
    """Compact with retired committed sources yields full prefix+suffix once."""
    before = _sha256(ARCHIVE) if ARCHIVE.exists() else ""
    _run([str(BIN), "compact", "--manifest", str(MANIFEST)])
    hdr = _read_ccf_header(ARCHIVE)
    assert len(hdr["time"]) >= 5
    # Prefix 0,30,60 plus suffix extras without duplicating identical overlap
    origin = UnitsOrigin.parse(hdr["units"])
    ordinals = [
        days_from_origin_to_ymd(hdr["calendar"], origin, t)
        for t in hdr["time"]
    ]
    assert ordinals == sorted(ordinals)
    assert len(ordinals) == len(set(ordinals))
    assert ARCHIVE.exists() and ROLLUP.exists() and REPORT.exists()
    assert before != _sha256(ARCHIVE) or len(hdr["time"]) >= 5


def test_mixed_origin_overlap_deduped() -> None:
    """Identical mixed-origin boundary row appears once."""
    _run([str(BIN), "compact", "--manifest", str(MANIFEST)])
    hdr = _read_ccf_header(ARCHIVE)
    origin = UnitsOrigin.parse(hdr["units"])
    ymds = [days_from_origin_to_ymd(hdr["calendar"], origin, t) for t in hdr["time"]]
    assert len(ymds) == len(set(ymds))


def test_conflict_rejects_without_replacing_committed() -> None:
    """Conflicting same-instant payloads fail atomically."""
    _run([str(BIN), "compact", "--manifest", str(MANIFEST)])
    snap = _snapshot_outputs()

    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)
        state = tdp / "state"
        shutil.copytree(STATE, state, dirs_exist_ok=True)
        segs = tdp / "segments"
        segs.mkdir()
        # Copy surviving good suffix then add conflicting segment
        for p in SEGMENTS.glob("*"):
            shutil.copy2(p, segs / p.name)
        bad = segs / "conflict.ccf"
        # Same calendar instant as archive day 90-ish with different temp
        build_axis_file(
            bad,
            calendar="360_day",
            units="days since 1900-01-01 00:00:00",
            times=[90.0],
            temp=[999.0],
            seed_tag="conflict",
        )
        # Also write precip-compatible fuller file via write_ccf
        write_ccf(
            bad,
            {
                "schema_version": 1,
                "calendar": "360_day",
                "units": "days since 1900-01-01 00:00:00",
                "time": [90.0],
                "bounds": [[75.0, 105.0]],
                "variables": {
                    "temp": {"dtype": "f64", "offset": 0, "count": 1, "agg": "mean"},
                    "precip": {"dtype": "f64", "offset": 8, "count": 1, "agg": "sum"},
                },
            },
            f64_bytes([999.0]) + f64_bytes([0.0]),
        )
        # First ensure 90 exists from prior compact — conflict against existing
        write_ccf(
            bad,
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
            f64_bytes([777.0]) + f64_bytes([0.1]),
        )
        man = tdp / "m.toml"
        man.write_text(
            f'''schema_version = 1
calendar = "360_day"
units = "days since 1900-01-01 00:00:00"
state_dir = "{state}"
archive_path = "{ARCHIVE}"
rollup_path = "{ROLLUP}"
report_path = "{REPORT}"
run_id = "conflict"
cache_dir = "{tdp / "cache"}"

[[sources]]
path = "{bad}"
role = "segment"
'''
        )
        # Reset checkpoint completed so bad is processed; keep archive
        ck = json.loads((state / "checkpoint.json").read_text())
        ck["completed_source_paths"] = [
            p for p in ck.get("completed_source_paths", []) if "_retired" in p
        ]
        (state / "checkpoint.json").write_text(json.dumps(ck, indent=2))
        proc = _run([str(BIN), "compact", "--manifest", str(man)], check=False)
        assert proc.returncode != 0
        assert ARCHIVE.read_bytes() == snap["archive"]
        assert ROLLUP.read_bytes() == snap["rollup"]
        assert REPORT.read_bytes() == snap["report"]


def test_report_matches_committed_digests() -> None:
    """Lineage report matches committed artifacts and required contract fields."""
    _run([str(BIN), "compact", "--manifest", str(MANIFEST)])
    report = json.loads(REPORT.read_text())
    hdr, _payload = _read_ccf(ARCHIVE)

    assert report["report_format_version"] == REPORT_FORMAT_VERSION
    assert isinstance(report["committed_generation_id"], str)
    assert report["committed_generation_id"]
    assert report["archive_digest"] == _sha256(ARCHIVE)
    assert report["rollup_digest"] == _sha256(ROLLUP)
    assert report["observation_count"] == len(hdr["time"])
    assert report["conflict"] is False
    assert report["recovery_outcome"] in {"resumed", "completed", "fresh", "idempotent"}

    assert isinstance(report["first_instant"], list) and len(report["first_instant"]) == 3
    assert isinstance(report["last_instant"], list) and len(report["last_instant"]) == 3
    origin = UnitsOrigin.parse(hdr["units"])
    first = list(days_from_origin_to_ymd(hdr["calendar"], origin, hdr["time"][0]))
    last = list(days_from_origin_to_ymd(hdr["calendar"], origin, hdr["time"][-1]))
    assert report["first_instant"] == first
    assert report["last_instant"] == last

    lineage = report["source_lineage"]
    assert isinstance(lineage, list) and lineage
    for entry in lineage:
        assert set(entry) >= {"path", "digest", "retired", "observation_count"}
        assert isinstance(entry["path"], str) and entry["path"]
        assert isinstance(entry["digest"], str) and len(entry["digest"]) == 64
        assert isinstance(entry["retired"], bool)
        assert isinstance(entry["observation_count"], int) and entry["observation_count"] >= 0

    retired = [e for e in lineage if e["retired"]]
    active = [e for e in lineage if not e["retired"]]
    assert retired, "retired committed prefix must appear in source_lineage"
    assert active, "surviving sources must appear in source_lineage"
    for e in retired:
        assert "_retired" in e["path"] or not Path(e["path"]).exists()


def test_archive_and_monthly_payload_alignment() -> None:
    """Archive rows stay aligned; monthly rollup is a valid climatological reduction."""
    _run([str(BIN), "compact", "--manifest", str(MANIFEST)])
    arch_hdr, arch_payload = _read_ccf(ARCHIVE)
    mon_hdr, mon_payload = _read_ccf(ROLLUP)

    _assert_header_payload_alignment(arch_hdr, arch_payload)
    _assert_header_payload_alignment(mon_hdr, mon_payload)

    assert arch_hdr["calendar"] == mon_hdr["calendar"]
    assert len(mon_hdr["time"]) >= 1
    assert len(mon_hdr["time"]) <= len(arch_hdr["time"])
    assert set(mon_hdr["variables"]) == set(arch_hdr["variables"])

    origin = UnitsOrigin.parse(arch_hdr["units"])
    arch_months = {
        days_from_origin_to_ymd(arch_hdr["calendar"], origin, t)[:2]
        for t in arch_hdr["time"]
    }
    mon_origin = UnitsOrigin.parse(mon_hdr["units"])
    mon_months = [
        days_from_origin_to_ymd(mon_hdr["calendar"], mon_origin, t)[:2]
        for t in mon_hdr["time"]
    ]
    assert len(mon_months) == len(set(mon_months))
    assert set(mon_months) == arch_months

    # Independent monthly resample of the committed archive must match values.
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "recomputed-monthly.ccf"
        _run(
            [
                str(BIN),
                "resample",
                "--in",
                str(ARCHIVE),
                "--freq",
                "mon",
                "--out",
                str(out),
                "--cache-dir",
                str(Path(td) / "cache"),
            ]
        )
        re_hdr, re_payload = _read_ccf(out)
        assert re_hdr["time"] == mon_hdr["time"]
        assert set(re_hdr["variables"]) == set(mon_hdr["variables"])
        for name, meta in mon_hdr["variables"].items():
            got = _read_f64_column(mon_payload, meta["offset"], meta["count"])
            exp_meta = re_hdr["variables"][name]
            exp = _read_f64_column(re_payload, exp_meta["offset"], exp_meta["count"])
            assert got == exp, f"monthly {name} mismatch: {got} vs {exp}"


def test_idempotent_three_runs() -> None:
    """Successful compact is byte-stable across repeats."""
    _run([str(BIN), "compact", "--manifest", str(MANIFEST)])
    a1, r1, p1 = ARCHIVE.read_bytes(), ROLLUP.read_bytes(), REPORT.read_bytes()
    _run([str(BIN), "compact", "--manifest", str(MANIFEST)])
    _run([str(BIN), "compact", "--manifest", str(MANIFEST)])
    assert ARCHIVE.read_bytes() == a1
    assert ROLLUP.read_bytes() == r1
    assert REPORT.read_bytes() == p1


def test_cache_equals_nocache_monthly() -> None:
    """Cached monthly rollup matches a no-cache recompute."""
    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)
        out1 = tdp / "m1.ccf"
        out2 = tdp / "m2.ccf"
        cache = tdp / "cache"
        _run(
            [
                str(BIN),
                "resample",
                "--in",
                str(SAMPLES / "resample_tricalendar.ccf"),
                "--freq",
                "mon",
                "--out",
                str(out1),
                "--cache-dir",
                str(cache),
            ]
        )
        _run(
            [
                str(BIN),
                "--no-cache",
                "resample",
                "--in",
                str(SAMPLES / "resample_tricalendar.ccf"),
                "--freq",
                "mon",
                "--out",
                str(out2),
                "--cache-dir",
                str(cache),
            ]
        )
        assert out1.read_bytes() == out2.read_bytes()


def test_same_path_source_replacement_is_applied() -> None:
    """Replacing bytes at an already-listed path is not skipped."""
    _run([str(BIN), "compact", "--manifest", str(MANIFEST)])
    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)
        state = tdp / "state"
        shutil.copytree(STATE, state)
        segs = tdp / "segments"
        segs.mkdir()
        target = segs / "extra_segment.ccf"
        # Initial version already "completed"
        write_ccf(
            target,
            {
                "schema_version": 1,
                "calendar": "360_day",
                "units": "days since 1900-01-01 00:00:00",
                "time": [210.0],
                "bounds": [[195.0, 225.0]],
                "variables": {
                    "temp": {"dtype": "f64", "offset": 0, "count": 1, "agg": "mean"},
                    "precip": {"dtype": "f64", "offset": 8, "count": 1, "agg": "sum"},
                },
            },
            f64_bytes([20.0]) + f64_bytes([5.0]),
        )
        old_digest = _sha256(target)
        ck = json.loads((state / "checkpoint.json").read_text())
        ck["completed_source_paths"] = list(
            set(ck.get("completed_source_paths", [])) | {str(target)}
        )
        (state / "checkpoint.json").write_text(json.dumps(ck, indent=2))
        lineage = json.loads((state / "lineage.json").read_text())
        lineage.setdefault("records", []).append(
            {
                "path": str(target),
                "digest": old_digest,
                "retired": False,
                "observation_count": 1,
            }
        )
        (state / "lineage.json").write_text(json.dumps(lineage, indent=2))
        # Replace with additional non-overlapping observation
        write_ccf(
            target,
            {
                "schema_version": 1,
                "calendar": "360_day",
                "units": "days since 1900-01-01 00:00:00",
                "time": [210.0, 240.0],
                "bounds": [[195.0, 225.0], [225.0, 255.0]],
                "variables": {
                    "temp": {"dtype": "f64", "offset": 0, "count": 2, "agg": "mean"},
                    "precip": {"dtype": "f64", "offset": 16, "count": 2, "agg": "sum"},
                },
            },
            f64_bytes([20.0, 21.0]) + f64_bytes([5.0, 5.5]),
        )
        man = tdp / "m.toml"
        man.write_text(
            f'''schema_version = 1
calendar = "360_day"
units = "days since 1900-01-01 00:00:00"
state_dir = "{state}"
archive_path = "{tdp / "archive.ccf"}"
rollup_path = "{tdp / "monthly.ccf"}"
report_path = "{tdp / "report.json"}"
run_id = "replace"
cache_dir = "{tdp / "cache"}"

[[sources]]
path = "{target}"
role = "segment"
'''
        )
        shutil.copy2(ARCHIVE, tdp / "archive.ccf")
        before_n = len(_read_ccf_header(tdp / "archive.ccf")["time"])
        _run([str(BIN), "compact", "--manifest", str(man)])
        after_n = len(_read_ccf_header(tdp / "archive.ccf")["time"])
        assert after_n > before_n


def test_convert_append_resample_regression() -> None:
    """Existing convert/append/resample/validate remain operational."""
    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)
        mid = tdp / "mid.cft"
        out = tdp / "out.ccf"
        _run([str(BIN), "convert", "--in", str(SAMPLES / "gregorian_monthly.ccf"), "--out", str(mid)])
        _run([str(BIN), "convert", "--in", str(mid), "--out", str(out)])
        assert _read_ccf_header(out)["calendar"] == "gregorian"
        merged = tdp / "merged.ccf"
        _run(
            [
                str(BIN),
                "append",
                "--base",
                str(SAMPLES / "append_base_360day.ccf"),
                "--append",
                str(SAMPLES / "append_tail_noleap.ccf"),
                "--out",
                str(merged),
            ]
        )
        mon = tdp / "mon.ccf"
        _run(
            [
                str(BIN),
                "resample",
                "--in",
                str(SAMPLES / "resample_tricalendar.ccf"),
                "--freq",
                "mon",
                "--out",
                str(mon),
            ]
        )
        _run([str(BIN), "validate", "--in", str(SAMPLES / "gregorian_monthly.ccf")])


def test_trace_schema_version() -> None:
    """Trace report uses documented schema_version 3."""
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "trace.json"
        _run(
            [
                str(BIN),
                "trace",
                "--manifest",
                "/app/data/trace-manifest.toml",
                "--out",
                str(out),
            ]
        )
        report = json.loads(out.read_text())
        assert report["schema_version"] == 3
        assert all(s["ok"] for s in report["scenarios"])


def test_fixture_integrity_segments_and_samples() -> None:
    """Bundled samples and surviving segments are not mutated by tests."""
    sample_digests = {p.name: _sha256(p) for p in SAMPLES.glob("*.ccf")}
    seg_digests = {p.name: _sha256(p) for p in SEGMENTS.glob("*")}
    _run([str(BIN), "compact", "--manifest", str(MANIFEST)])
    for name, dig in sample_digests.items():
        assert _sha256(SAMPLES / name) == dig
    for name, dig in seg_digests.items():
        assert _sha256(SEGMENTS / name) == dig


def test_hidden_generated_compaction(tmp_path: Path) -> None:
    """Deterministic alternate manifest still compacts coherently."""
    state = tmp_path / "state"
    state.mkdir()
    segs = tmp_path / "segs"
    segs.mkdir()
    a = segs / "a.ccf"
    b = segs / "b.ccf"
    write_ccf(
        a,
        {
            "schema_version": 1,
            "calendar": "noleap",
            "units": "days since 2000-01-01 00:00:00",
            "time": [0.0, 31.0],
            "variables": {
                "temp": {"dtype": "f64", "offset": 0, "count": 2, "agg": "mean"}
            },
        },
        f64_bytes([1.0, 2.0]),
    )
    write_ccf(
        b,
        {
            "schema_version": 1,
            "calendar": "noleap",
            "units": "days since 2000-01-01 00:00:00",
            "time": [62.0, 90.0],
            "variables": {
                "temp": {"dtype": "f64", "offset": 0, "count": 2, "agg": "mean"}
            },
        },
        f64_bytes([3.0, 4.0]),
    )
    arch = tmp_path / "archive.ccf"
    # Seed committed prefix as file a only
    shutil.copy2(a, arch)
    (state / "checkpoint.json").write_text(
        json.dumps(
            {
                "committed_generation_id": "h0",
                "planned_generation_id": None,
                "completed_source_paths": [str(a)],
                "archive_path": str(arch),
                "rollup_path": str(tmp_path / "monthly.ccf"),
                "report_path": str(tmp_path / "report.json"),
            },
            indent=2,
        )
    )
    (state / "lineage.json").write_text(
        json.dumps(
            {
                "records": [
                    {
                        "path": str(a),
                        "digest": _sha256(a),
                        "retired": False,
                        "observation_count": 2,
                    }
                ]
            },
            indent=2,
        )
    )
    (state / "journal.jsonl").write_text("")
    man = tmp_path / "m.toml"
    man.write_text(
        f'''schema_version = 1
calendar = "noleap"
units = "days since 2000-01-01 00:00:00"
state_dir = "{state}"
archive_path = "{arch}"
rollup_path = "{tmp_path / "monthly.ccf"}"
report_path = "{tmp_path / "report.json"}"
run_id = "hidden"
cache_dir = "{tmp_path / "cache"}"

[[sources]]
path = "{a}"
role = "committed"

[[sources]]
path = "{b}"
role = "segment"
'''
    )
    # Retire a
    a.unlink()
    _run([str(BIN), "compact", "--manifest", str(man)])
    hdr = _read_ccf_header(arch)
    assert len(hdr["time"]) == 4
    report = json.loads((tmp_path / "report.json").read_text())
    assert report["archive_digest"] == _sha256(arch)
