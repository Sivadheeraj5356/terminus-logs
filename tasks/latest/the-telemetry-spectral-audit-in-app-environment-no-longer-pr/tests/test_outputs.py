"""Verifier for Hann bin energy audit CLI (schema v2 and v3)."""

from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import pytest

BUNDLED_PACK = Path("/app/inputs/pack.json")
BUILD_DIR = Path("/app/build")
BINARY = BUILD_DIR / "hann_energy_audit"
INSTALLED_BINARY = Path("/app/bin/hann_energy_audit")
FLOAT_ABS_TOL = 1e-9
_TESTS_DIR = Path(__file__).resolve().parent
_DENY_SO: Path | None = None


def _deny_src() -> Path:
    matches = sorted(_TESTS_DIR.glob("_deny_*.c"))
    assert matches, "missing deny-access shim source under tests/"
    return matches[0]


def _deny_preload() -> Path:
    """Build an LD_PRELOAD shim that blocks /tests reads and Python execs."""
    global _DENY_SO
    if _DENY_SO is not None and _DENY_SO.is_file():
        return _DENY_SO
    so_path = Path(tempfile.mkstemp(prefix="deny_", suffix=".so")[1])
    subprocess.run(
        [
            "gcc",
            "-shared",
            "-fPIC",
            "-O2",
            "-o",
            str(so_path),
            str(_deny_src()),
            "-ldl",
        ],
        check=True,
        timeout=60,
    )
    _DENY_SO = so_path
    return so_path


def _cli_env() -> dict[str, str]:
    env = os.environ.copy()
    preload = str(_deny_preload())
    existing = env.get("LD_PRELOAD", "")
    env["LD_PRELOAD"] = preload if not existing else f"{preload}:{existing}"
    return env


def sha256_hex(payload: str) -> str:
    return hashlib.sha256(payload.encode()).hexdigest()


def format_fixed12(value: float) -> str:
    return f"{value:.12f}"


def hann_coefficients(n: int) -> list[float]:
    if n <= 1:
        return [1.0] * n
    return [0.5 * (1.0 - math.cos(2.0 * math.pi * i / (n - 1))) for i in range(n)]


def reconstruct_timeline_v3(scenario: dict[str, Any]) -> list[float | None]:
    timeline: list[float | None] = [None] * scenario["timeline_len"]
    for revision in scenario["sample_revisions"]:
        for op in revision["ops"]:
            timeline[op["index"]] = op["value"]
    gains = [1.0] * scenario["timeline_len"]
    offsets = [0.0] * scenario["timeline_len"]
    for revision in scenario["calibration_revisions"]:
        for op in revision["ops"]:
            for idx in range(op["start"], op["end"]):
                gains[idx] = op["gain"]
                offsets[idx] = op["offset"]
    calibrated: list[float | None] = []
    for idx, raw in enumerate(timeline):
        if raw is None:
            calibrated.append(None)
        else:
            calibrated.append(gains[idx] * raw + offsets[idx])
    return calibrated


def timeline_csv(timeline: list[float | None]) -> str:
    parts: list[str] = []
    for value in timeline:
        if value is None:
            parts.append("null")
        else:
            parts.append(format_fixed12(value))
    return ",".join(parts)


def revision_ids_csv(revisions: list[dict[str, Any]]) -> str:
    return ",".join(revision["revision_id"] for revision in revisions)


def lineage_hex(scenario: dict[str, Any], timeline: list[float | None]) -> str:
    seal = "|".join(
        [
            revision_ids_csv(scenario["sample_revisions"]),
            revision_ids_csv(scenario["calibration_revisions"]),
            timeline_csv(timeline),
        ]
    )
    return sha256_hex(seal)


def scenario_fingerprint_part(
    scenario: dict[str, Any], timeline: list[float | None]
) -> str:
    band_parts = "|".join(
        f"{band['name']}:{format_fixed12(band['low_hz'])}:"
        f"{format_fixed12(band['high_hz'])}:{format_fixed12(band['weight'])}"
        for band in scenario["bands"]
    )
    return "|".join(
        [
            scenario["id"],
            str(scenario["timeline_len"]),
            format_fixed12(scenario["sample_rate_hz"]),
            str(scenario["frame_len"]),
            str(scenario["hop_len"]),
            scenario["detrend"],
            scenario["gap_policy"],
            format_fixed12(scenario["min_frame_quality"]),
            band_parts,
            revision_ids_csv(scenario["sample_revisions"]),
            revision_ids_csv(scenario["calibration_revisions"]),
            timeline_csv(timeline),
        ]
    )


def pack_fingerprint(pack: dict[str, Any], timelines: list[list[float | None]]) -> str:
    parts = [str(pack["schema_version"])]
    for scenario, timeline in zip(pack["scenarios"], timelines, strict=True):
        parts.append(scenario_fingerprint_part(scenario, timeline))
    return sha256_hex("|".join(parts))


def frame_values(
    samples: list[float | None],
    start: int,
    frame_len: int,
    detrend: str,
    gap_policy: str,
) -> list[float] | None:
    chunk = samples[start : start + frame_len]
    if gap_policy == "skip_frame" and any(value is None for value in chunk):
        return None
    numeric = [value for value in chunk if value is not None]
    mean = sum(numeric) / len(numeric) if numeric else 0.0
    out: list[float] = []
    for value in chunk:
        if value is None:
            out.append(0.0)
        elif detrend == "mean":
            out.append(value - mean)
        else:
            out.append(value)
    return out


def select_bins(frame_len: int, sample_rate_hz: float, low_hz: float, high_hz: float) -> list[int]:
    bins: list[int] = []
    for k in range(frame_len // 2 + 1):
        freq = k * sample_rate_hz / frame_len
        if low_hz <= freq < high_hz:
            bins.append(k)
    return bins


def goertzel_magnitude_sq(windowed: list[float], k: int) -> float:
    n = len(windowed)
    omega = 2.0 * math.pi * k / n
    coeff = 2.0 * math.cos(omega)
    s0 = s1 = s2 = 0.0
    for sample in windowed:
        s0 = sample + coeff * s1 - s2
        s2, s1 = s1, s0
    real = s1 - s2 * math.cos(omega)
    imag = s2 * math.sin(omega)
    return real * real + imag * imag


def reference_scenario(
    spec: dict[str, Any], schema_version: int, timeline: list[float | None] | None = None
) -> dict[str, Any]:
    samples = timeline if timeline is not None else spec["samples"]
    frame_len = spec["frame_len"]
    hop_len = spec["hop_len"]
    sample_count = len(samples)
    valid_sample_count = sum(1 for value in samples if value is not None)
    coeffs = hann_coefficients(frame_len)
    window_energy = sum(c * c for c in coeffs)

    starts = list(range(0, sample_count - frame_len + 1, hop_len))
    retained: list[list[float]] = []
    dropped_frame_count = 0
    rejected_frame_count = 0
    for start in starts:
        chunk = samples[start : start + frame_len]
        if spec["gap_policy"] == "skip_frame" and any(value is None for value in chunk):
            dropped_frame_count += 1
            continue
        if schema_version >= 3:
            numeric_count = sum(1 for value in chunk if value is not None)
            frame_quality = numeric_count / frame_len
            if frame_quality < spec["min_frame_quality"]:
                rejected_frame_count += 1
                continue
        frame = frame_values(samples, start, frame_len, spec["detrend"], spec["gap_policy"])
        assert frame is not None
        retained.append([frame[i] * coeffs[i] for i in range(frame_len)])

    frame_count = len(retained)
    bands_out: list[dict[str, Any]] = []
    for band in spec["bands"]:
        weight = band["weight"] if schema_version >= 3 else 1.0
        bins = select_bins(frame_len, spec["sample_rate_hz"], band["low_hz"], band["high_hz"])
        raw_energy = 0.0
        peak_sums = {k: 0.0 for k in bins}
        for windowed in retained:
            for k in bins:
                magnitude_sq = goertzel_magnitude_sq(windowed, k)
                raw_energy += weight * magnitude_sq
                peak_sums[k] += magnitude_sq

        if frame_count == 0 or frame_len == 0 or window_energy <= 0.0 or not bins:
            energy = 0.0
            peak_bin = -1
            peak_hz = 0.0
        else:
            energy = raw_energy / (frame_count * frame_len * frame_len * window_energy)
            best_val = max(peak_sums.values())
            peak_bin = min(k for k in bins if peak_sums[k] == best_val)
            peak_hz = peak_bin * spec["sample_rate_hz"] / frame_len

        band_row: dict[str, Any] = {
            "name": band["name"],
            "low_hz": band["low_hz"],
            "high_hz": band["high_hz"],
            "bin_count": len(bins),
            "peak_bin": peak_bin,
            "peak_hz": peak_hz,
            "energy": energy,
        }
        if schema_version >= 3:
            band_row["weight"] = weight
        bands_out.append(band_row)

    row: dict[str, Any] = {
        "id": spec["id"],
        "sample_count": sample_count,
        "valid_sample_count": valid_sample_count,
        "frame_len": frame_len,
        "hop_len": hop_len,
        "frame_count": frame_count,
        "dropped_frame_count": dropped_frame_count,
        "window_energy": window_energy,
        "bands": bands_out,
    }
    if schema_version >= 3:
        row["rejected_frame_count"] = rejected_frame_count
        row["lineage_hex"] = lineage_hex(spec, samples)
    row["digest_hex"] = scenario_digest(row, schema_version)
    return row


def scenario_digest(row: dict[str, Any], schema_version: int) -> str:
    parts = [
        row["id"],
        str(row["sample_count"]),
        str(row["valid_sample_count"]),
        str(row["frame_len"]),
        str(row["hop_len"]),
        str(row["frame_count"]),
        str(row["dropped_frame_count"]),
    ]
    if schema_version >= 3:
        parts.append(str(row["rejected_frame_count"]))
    parts.append(format_fixed12(row["window_energy"]))
    if schema_version >= 3:
        parts.append(row["lineage_hex"])
    for band in row["bands"]:
        if schema_version >= 3:
            parts.append(
                f"{band['name']}:{format_fixed12(band['low_hz'])}:"
                f"{format_fixed12(band['high_hz'])}:{format_fixed12(band['weight'])}:"
                f"{band['bin_count']}:{band['peak_bin']}:{format_fixed12(band['peak_hz'])}:"
                f"{format_fixed12(band['energy'])}"
            )
        else:
            parts.append(
                f"{band['name']}:{format_fixed12(band['low_hz'])}:"
                f"{format_fixed12(band['high_hz'])}:{band['bin_count']}:{band['peak_bin']}:"
                f"{format_fixed12(band['peak_hz'])}:{format_fixed12(band['energy'])}"
            )
    return sha256_hex("|".join(parts))


def summary_digest(report: dict[str, Any]) -> str:
    summary = report["summary"]
    parts = [
        str(report["schema_version"]),
        str(summary["scenario_count"]),
        str(summary["band_result_count"]),
        str(summary["total_frame_count"]),
        str(summary["total_dropped_frames"]),
    ]
    if report["schema_version"] >= 3:
        parts.append(str(summary["total_rejected_frames"]))
    parts.extend(row["digest_hex"] for row in report["scenarios"])
    return sha256_hex("|".join(parts))


def reference_report(pack: dict[str, Any]) -> dict[str, Any]:
    schema_version = pack["schema_version"]
    scenarios: list[dict[str, Any]] = []
    for spec in pack["scenarios"]:
        if schema_version >= 3:
            timeline = reconstruct_timeline_v3(spec)
            scenarios.append(reference_scenario(spec, schema_version, timeline))
        else:
            scenarios.append(reference_scenario(spec, schema_version))
    summary: dict[str, Any] = {
        "scenario_count": len(scenarios),
        "band_result_count": sum(len(row["bands"]) for row in scenarios),
        "total_frame_count": sum(row["frame_count"] for row in scenarios),
        "total_dropped_frames": sum(row["dropped_frame_count"] for row in scenarios),
    }
    if schema_version >= 3:
        summary["total_rejected_frames"] = sum(row["rejected_frame_count"] for row in scenarios)
    report = {"schema_version": schema_version, "scenarios": scenarios, "summary": summary}
    report["summary"]["digest_hex"] = summary_digest(report)
    return report


def rebuild_binary() -> Path:
    shutil.rmtree(BUILD_DIR, ignore_errors=True)
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "cmake",
            "-S",
            "/app/environment",
            "-B",
            str(BUILD_DIR),
            "-DCMAKE_BUILD_TYPE=Release",
            "-DCMAKE_INSTALL_PREFIX=/app",
        ],
        check=True,
        timeout=300,
    )
    subprocess.run(["cmake", "--build", str(BUILD_DIR), "-j2"], check=True, timeout=300)
    subprocess.run(["cmake", "--install", str(BUILD_DIR)], check=True, timeout=120)
    assert BINARY.is_file(), "hann_energy_audit binary was not produced by the build"
    return BINARY


def run_cli(
    pack_dict: dict[str, Any],
    out_path: Path,
    checkpoint_path: Path | None = None,
    *,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    with tempfile.TemporaryDirectory(prefix="hann_pack_") as tmp:
        pack_path = Path(tmp) / "pack.json"
        pack_path.write_text(json.dumps(pack_dict), encoding="utf-8")
        cmd = [str(INSTALLED_BINARY), "--pack", str(pack_path), "--out", str(out_path)]
        if checkpoint_path is not None:
            cmd.extend(["--checkpoint", str(checkpoint_path)])
        return subprocess.run(
            cmd,
            check=check,
            timeout=60,
            capture_output=True,
            text=True,
            env=_cli_env(),
        )


def run_cli_report(
    pack_dict: dict[str, Any],
    out_path: Path,
    checkpoint_path: Path | None = None,
) -> dict[str, Any]:
    run_cli(pack_dict, out_path, checkpoint_path)
    return json.loads(out_path.read_text(encoding="utf-8"))


def floats_close(got: float, expected: float) -> bool:
    return math.isclose(got, expected, rel_tol=0.0, abs_tol=FLOAT_ABS_TOL)


def deterministic_jitter(index: int) -> float:
    return ((index * 48271) % 1000) / 100000.0 - 0.005


def assert_report_matches(got: dict[str, Any], expected: dict[str, Any]) -> None:
    assert got["schema_version"] == expected["schema_version"]
    assert len(got["scenarios"]) == len(expected["scenarios"])
    for got_row, exp_row in zip(got["scenarios"], expected["scenarios"], strict=True):
        assert got_row["id"] == exp_row["id"]
        assert got_row["sample_count"] == exp_row["sample_count"]
        assert got_row["valid_sample_count"] == exp_row["valid_sample_count"]
        assert got_row["frame_len"] == exp_row["frame_len"]
        assert got_row["hop_len"] == exp_row["hop_len"]
        assert got_row["frame_count"] == exp_row["frame_count"]
        assert got_row["dropped_frame_count"] == exp_row["dropped_frame_count"]
        if expected["schema_version"] >= 3:
            assert got_row["rejected_frame_count"] == exp_row["rejected_frame_count"]
            assert got_row["lineage_hex"] == exp_row["lineage_hex"]
        assert floats_close(got_row["window_energy"], exp_row["window_energy"])
        assert got_row["digest_hex"] == exp_row["digest_hex"]
        assert len(got_row["bands"]) == len(exp_row["bands"])
        for got_band, exp_band in zip(got_row["bands"], exp_row["bands"], strict=True):
            assert got_band["name"] == exp_band["name"]
            assert floats_close(got_band["low_hz"], exp_band["low_hz"])
            assert floats_close(got_band["high_hz"], exp_band["high_hz"])
            if expected["schema_version"] >= 3:
                assert floats_close(got_band["weight"], exp_band["weight"])
            assert got_band["bin_count"] == exp_band["bin_count"]
            assert got_band["peak_bin"] == exp_band["peak_bin"]
            assert floats_close(got_band["peak_hz"], exp_band["peak_hz"])
            assert floats_close(got_band["energy"], exp_band["energy"])

    got_summary = got["summary"]
    exp_summary = expected["summary"]
    assert got_summary["scenario_count"] == exp_summary["scenario_count"]
    assert got_summary["band_result_count"] == exp_summary["band_result_count"]
    assert got_summary["total_frame_count"] == exp_summary["total_frame_count"]
    assert got_summary["total_dropped_frames"] == exp_summary["total_dropped_frames"]
    if expected["schema_version"] >= 3:
        assert got_summary["total_rejected_frames"] == exp_summary["total_rejected_frames"]
    assert got_summary["digest_hex"] == exp_summary["digest_hex"]


def make_v3_scenario(
    scenario_id: str,
    *,
    timeline_len: int = 48,
    frame_len: int = 16,
    hop_len: int = 8,
    min_frame_quality: float = 0.75,
    sample_rate_hz: float = 256.0,
) -> dict[str, Any]:
    return {
        "id": scenario_id,
        "sample_rate_hz": sample_rate_hz,
        "frame_len": frame_len,
        "hop_len": hop_len,
        "detrend": "none",
        "gap_policy": "zero_fill",
        "min_frame_quality": min_frame_quality,
        "timeline_len": timeline_len,
        "bands": [
            {"name": "tone", "low_hz": 45.0, "high_hz": 55.0, "weight": 1.25},
            {"name": "wide", "low_hz": 20.0, "high_hz": 80.0, "weight": 0.5},
        ],
        "sample_revisions": [],
        "calibration_revisions": [],
    }


@pytest.fixture(scope="session")
def audit_bin() -> Path:
    return rebuild_binary()


def test_bundled_schema_v2_report_matches_reference(audit_bin: Path) -> None:
    """Bundled schema-version 2 pack report matches the contract reference."""
    pack = json.loads(BUNDLED_PACK.read_text(encoding="utf-8"))
    expected = reference_report(pack)
    with tempfile.TemporaryDirectory(prefix="hann_out_") as tmp:
        got = run_cli_report(pack, Path(tmp) / "report.json")
    assert_report_matches(got, expected)


def test_bundled_pack_writes_canonical_output_path(audit_bin: Path) -> None:
    """Bundled pack is written to the canonical /app/output/report.json path via the CLI."""
    pack = json.loads(BUNDLED_PACK.read_text(encoding="utf-8"))
    expected = reference_report(pack)
    out_path = Path("/app/output/report.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [str(INSTALLED_BINARY), "--pack", str(BUNDLED_PACK), "--out", str(out_path)],
        check=True,
        timeout=60,
        env=_cli_env(),
    )
    got = json.loads(out_path.read_text(encoding="utf-8"))
    assert_report_matches(got, expected)


def test_dynamic_non_power_of_two_overlap_and_phase_shift(audit_bin: Path) -> None:
    """Overlapping non-power-of-two frames with mixed tones match reference energies."""
    frame_len = 45
    hop_len = 11
    sample_rate_hz = 441.0
    sample_count = 120
    samples: list[float] = []
    for i in range(sample_count):
        t = i / sample_rate_hz
        value = (
            math.sin(2.0 * math.pi * 37.0 * t + 0.3)
            + 0.7 * math.sin(2.0 * math.pi * 83.0 * t + 1.1)
            + 0.2 * math.sin(2.0 * math.pi * 129.0 * t + 2.4)
        )
        samples.append(value + deterministic_jitter(i))

    pack = {
        "schema_version": 2,
        "scenarios": [
            {
                "id": "phase_shift_overlap",
                "sample_rate_hz": sample_rate_hz,
                "frame_len": frame_len,
                "hop_len": hop_len,
                "detrend": "none",
                "gap_policy": "zero_fill",
                "bands": [
                    {"name": "low", "low_hz": 30.0, "high_hz": 50.0},
                    {"name": "mid", "low_hz": 70.0, "high_hz": 95.0},
                    {"name": "high", "low_hz": 120.0, "high_hz": 140.0},
                ],
                "samples": samples,
            }
        ],
    }
    expected = reference_report(pack)
    with tempfile.TemporaryDirectory(prefix="hann_dyn_") as tmp:
        got = run_cli_report(pack, Path(tmp) / "report.json")
    assert_report_matches(got, expected)


def test_gap_policy_zero_fill_vs_skip_frame(audit_bin: Path) -> None:
    """zero_fill retains more frames than skip_frame on the same gapped series."""
    samples: list[float | None] = [1.0, 0.5, None, -0.5, -1.0, -0.5, None, 0.5] * 6
    base = {
        "sample_rate_hz": 240.0,
        "frame_len": 8,
        "hop_len": 4,
        "detrend": "none",
        "bands": [{"name": "wide", "low_hz": 20.0, "high_hz": 80.0}],
        "samples": samples,
    }
    pack = {
        "schema_version": 2,
        "scenarios": [
            {**base, "id": "zero_fill_case", "gap_policy": "zero_fill"},
            {**base, "id": "skip_frame_case", "gap_policy": "skip_frame"},
        ],
    }
    expected = reference_report(pack)
    with tempfile.TemporaryDirectory(prefix="hann_gap_") as tmp:
        got = run_cli_report(pack, Path(tmp) / "report.json")
    assert_report_matches(got, expected)
    zero_row = got["scenarios"][0]
    skip_row = got["scenarios"][1]
    assert zero_row["frame_count"] > skip_row["frame_count"]
    assert skip_row["dropped_frame_count"] > zero_row["dropped_frame_count"]


def test_mean_detrend_changes_dc_dominated_frames(audit_bin: Path) -> None:
    """Mean detrending changes band energy on DC-dominated frames."""
    frame_len = 32
    sample_rate_hz = 320.0
    samples = [
        8.0 + 0.05 * math.sin(2.0 * math.pi * 50.0 * i / sample_rate_hz) + deterministic_jitter(i) * 1e-2
        for i in range(frame_len)
    ]
    base = {
        "sample_rate_hz": sample_rate_hz,
        "frame_len": frame_len,
        "hop_len": frame_len,
        "gap_policy": "zero_fill",
        "bands": [{"name": "tone", "low_hz": 45.0, "high_hz": 55.0}],
        "samples": samples,
    }
    pack = {
        "schema_version": 2,
        "scenarios": [
            {**base, "id": "dc_no_detrend", "detrend": "none"},
            {**base, "id": "dc_mean_removed", "detrend": "mean"},
        ],
    }
    expected = reference_report(pack)
    with tempfile.TemporaryDirectory(prefix="hann_detrend_") as tmp:
        got = run_cli_report(pack, Path(tmp) / "report.json")
    assert_report_matches(got, expected)
    none_energy = got["scenarios"][0]["bands"][0]["energy"]
    mean_energy = got["scenarios"][1]["bands"][0]["energy"]
    assert abs(none_energy - mean_energy) > 1e-6


def test_half_open_edges_and_empty_band(audit_bin: Path) -> None:
    """Half-open band edges include the lower frequency and can yield empty bands."""
    frame_len = 32
    sample_rate_hz = 320.0
    samples = [math.sin(2.0 * math.pi * 50.0 * i / sample_rate_hz) for i in range(frame_len)]
    pack = {
        "schema_version": 2,
        "scenarios": [
            {
                "id": "lower_included",
                "sample_rate_hz": sample_rate_hz,
                "frame_len": frame_len,
                "hop_len": frame_len,
                "detrend": "none",
                "gap_policy": "zero_fill",
                "bands": [{"name": "edge", "low_hz": 50.0, "high_hz": 160.0}],
                "samples": samples,
            },
            {
                "id": "upper_excluded",
                "sample_rate_hz": sample_rate_hz,
                "frame_len": frame_len,
                "hop_len": frame_len,
                "detrend": "none",
                "gap_policy": "zero_fill",
                "bands": [{"name": "narrow", "low_hz": 150.0, "high_hz": 160.0}],
                "samples": samples,
            },
            {
                "id": "empty_band",
                "sample_rate_hz": sample_rate_hz,
                "frame_len": frame_len,
                "hop_len": frame_len,
                "detrend": "none",
                "gap_policy": "zero_fill",
                "bands": [{"name": "void", "low_hz": 155.0, "high_hz": 157.0}],
                "samples": samples,
            },
        ],
    }
    expected = reference_report(pack)
    with tempfile.TemporaryDirectory(prefix="hann_edge_") as tmp:
        got = run_cli_report(pack, Path(tmp) / "report.json")
    assert_report_matches(got, expected)
    lower_row = got["scenarios"][0]
    upper_row = got["scenarios"][1]
    empty_row = got["scenarios"][2]
    assert lower_row["bands"][0]["bin_count"] > upper_row["bands"][0]["bin_count"]
    assert empty_row["bands"][0]["bin_count"] == 0
    assert empty_row["bands"][0]["peak_bin"] == -1
    assert empty_row["bands"][0]["peak_hz"] == 0.0
    assert empty_row["bands"][0]["energy"] == 0.0


def test_schema_v3_revision_replay_and_calibration(audit_bin: Path) -> None:
    """Schema v3 sample and calibration revisions replay into calibrated timelines."""
    scenario = make_v3_scenario("rev_cal")
    scenario["sample_revisions"] = [
        {
            "revision_id": "s1",
            "ops": [
                {"index": 0, "value": 1.0},
                {"index": 1, "value": 0.5},
                {"index": 2, "value": None},
            ],
        },
        {
            "revision_id": "s2",
            "ops": [
                {"index": 2, "value": -0.25},
                {"index": 3, "value": 0.75},
            ],
        },
    ]
    for idx in range(4, scenario["timeline_len"]):
        scenario["sample_revisions"][1]["ops"].append(
            {"index": idx, "value": math.sin(2.0 * math.pi * 50.0 * idx / scenario["sample_rate_hz"])}
        )
    scenario["calibration_revisions"] = [
        {
            "revision_id": "c1",
            "ops": [{"start": 0, "end": 16, "gain": 2.0, "offset": 0.1}],
        },
        {
            "revision_id": "c2",
            "ops": [{"start": 8, "end": 24, "gain": 1.5, "offset": -0.2}],
        },
    ]
    pack = {"schema_version": 3, "scenarios": [scenario]}
    expected = reference_report(pack)
    with tempfile.TemporaryDirectory(prefix="hann_v3_rev_") as tmp:
        got = run_cli_report(pack, Path(tmp) / "report.json")
    assert_report_matches(got, expected)


def test_schema_v3_frame_quality_rejection(audit_bin: Path) -> None:
    """Frames below min_frame_quality are rejected and counted."""
    scenario = make_v3_scenario("quality_gate", timeline_len=32, frame_len=8, hop_len=4, min_frame_quality=0.875)
    ops: list[dict[str, Any]] = []
    for idx in range(scenario["timeline_len"]):
        if idx % 4 == 2:
            ops.append({"index": idx, "value": None})
        else:
            ops.append({"index": idx, "value": math.sin(2.0 * math.pi * 50.0 * idx / scenario["sample_rate_hz"])})
    scenario["sample_revisions"] = [{"revision_id": "sparse", "ops": ops}]
    pack = {"schema_version": 3, "scenarios": [scenario]}
    expected = reference_report(pack)
    with tempfile.TemporaryDirectory(prefix="hann_v3_q_") as tmp:
        got = run_cli_report(pack, Path(tmp) / "report.json")
    assert_report_matches(got, expected)
    assert got["scenarios"][0]["rejected_frame_count"] > 0


def test_schema_v3_weighted_bands_change_energy(audit_bin: Path) -> None:
    """Band weight scales reported energy for identical bin selections."""
    scenario = make_v3_scenario("weighted", timeline_len=32, frame_len=16, hop_len=16, min_frame_quality=0.5)
    scenario["bands"] = [
        {"name": "unit", "low_hz": 45.0, "high_hz": 55.0, "weight": 1.0},
        {"name": "heavy", "low_hz": 45.0, "high_hz": 55.0, "weight": 4.0},
    ]
    ops = [
        {"index": idx, "value": math.sin(2.0 * math.pi * 50.0 * idx / scenario["sample_rate_hz"])}
        for idx in range(scenario["timeline_len"])
    ]
    scenario["sample_revisions"] = [{"revision_id": "fill", "ops": ops}]
    pack = {"schema_version": 3, "scenarios": [scenario]}
    expected = reference_report(pack)
    with tempfile.TemporaryDirectory(prefix="hann_v3_w_") as tmp:
        got = run_cli_report(pack, Path(tmp) / "report.json")
    assert_report_matches(got, expected)
    unit_energy = got["scenarios"][0]["bands"][0]["energy"]
    heavy_energy = got["scenarios"][0]["bands"][1]["energy"]
    assert heavy_energy > unit_energy * 3.5


def test_semantically_equivalent_v3_packs_byte_identical_reports(audit_bin: Path) -> None:
    """Semantically equivalent revision graphs produce byte-identical reports."""
    base = make_v3_scenario("equiv", timeline_len=24, frame_len=12, hop_len=6, min_frame_quality=0.5)
    values = [math.sin(2.0 * math.pi * 40.0 * idx / base["sample_rate_hz"]) for idx in range(base["timeline_len"])]
    pack_a = {
        "schema_version": 3,
        "scenarios": [
            {
                **base,
                "sample_revisions": [
                    {"revision_id": "a1", "ops": [{"index": i, "value": values[i]} for i in range(12)]},
                    {"revision_id": "a2", "ops": [{"index": i, "value": values[i]} for i in range(12, 24)]},
                ],
            }
        ],
    }
    pack_b = {
        "schema_version": 3,
        "scenarios": [
            {
                **base,
                "sample_revisions": [
                    {"revision_id": "a1", "ops": [{"index": i, "value": values[i]} for i in range(0, 24, 2)]},
                    {"revision_id": "a2", "ops": [{"index": i, "value": values[i]} for i in range(1, 24, 2)]},
                ],
            }
        ],
    }
    with tempfile.TemporaryDirectory(prefix="hann_v3_eq_") as tmp:
        out_a = Path(tmp) / "a.json"
        out_b = Path(tmp) / "b.json"
        report_a = run_cli_report(pack_a, out_a)
        report_b = run_cli_report(pack_b, out_b)
        assert_report_matches(report_a, reference_report(pack_a))
        assert_report_matches(report_b, reference_report(pack_b))
        assert out_a.read_text(encoding="utf-8") == out_b.read_text(encoding="utf-8")


def test_different_revision_ids_change_lineage_not_metrics(audit_bin: Path) -> None:
    """Revision ids change lineage and digests without changing band energies."""
    base = make_v3_scenario("lineage", timeline_len=16, frame_len=8, hop_len=8, min_frame_quality=0.5)
    values = [math.sin(2.0 * math.pi * 50.0 * idx / base["sample_rate_hz"]) for idx in range(base["timeline_len"])]
    ops = [{"index": idx, "value": values[idx]} for idx in range(base["timeline_len"])]
    pack_a = {
        "schema_version": 3,
        "scenarios": [{**base, "sample_revisions": [{"revision_id": "alpha", "ops": ops}]}],
    }
    pack_b = {
        "schema_version": 3,
        "scenarios": [{**base, "sample_revisions": [{"revision_id": "beta", "ops": ops}]}],
    }
    ref_a = reference_report(pack_a)
    ref_b = reference_report(pack_b)
    with tempfile.TemporaryDirectory(prefix="hann_v3_lin_") as tmp:
        got_a = run_cli_report(pack_a, Path(tmp) / "a.json")
        got_b = run_cli_report(pack_b, Path(tmp) / "b.json")
    assert got_a["scenarios"][0]["bands"][0]["energy"] == pytest.approx(
        got_b["scenarios"][0]["bands"][0]["energy"], abs=FLOAT_ABS_TOL
    )
    assert ref_a["scenarios"][0]["lineage_hex"] != ref_b["scenarios"][0]["lineage_hex"]
    assert got_a["scenarios"][0]["lineage_hex"] != got_b["scenarios"][0]["lineage_hex"]
    assert got_a["scenarios"][0]["digest_hex"] != got_b["scenarios"][0]["digest_hex"]


def test_checkpoint_resume_validates_matching_state(audit_bin: Path) -> None:
    """Matching checkpoints resume and preserve report bytes."""
    scenario = make_v3_scenario("resume_ok", timeline_len=32, frame_len=16, hop_len=8, min_frame_quality=0.5)
    ops = [
        {"index": idx, "value": math.sin(2.0 * math.pi * 50.0 * idx / scenario["sample_rate_hz"])}
        for idx in range(scenario["timeline_len"])
    ]
    scenario["sample_revisions"] = [{"revision_id": "seed", "ops": ops}]
    pack = {"schema_version": 3, "scenarios": [scenario]}
    with tempfile.TemporaryDirectory(prefix="hann_ckpt_ok_") as tmp:
        out_path = Path(tmp) / "report.json"
        ckpt_path = Path(tmp) / "state.json"
        first = run_cli_report(pack, out_path, ckpt_path)
        first_bytes = out_path.read_bytes()
        second = run_cli_report(pack, out_path, ckpt_path)
        assert_report_matches(first, reference_report(pack))
        assert_report_matches(second, first)
        assert out_path.read_bytes() == first_bytes
        checkpoint = json.loads(ckpt_path.read_text(encoding="utf-8"))
        timelines = [reconstruct_timeline_v3(scenario)]
        assert checkpoint["pack_fingerprint"] == pack_fingerprint(pack, timelines)
        assert checkpoint["completed"][0]["digest_hex"] == first["scenarios"][0]["digest_hex"]


def test_stale_checkpoint_fingerprint_leaves_outputs_unchanged(audit_bin: Path) -> None:
    """Stale pack fingerprints fail without rewriting report or checkpoint bytes."""
    scenario = make_v3_scenario("stale", timeline_len=24, frame_len=12, hop_len=6, min_frame_quality=0.5)
    ops = [
        {"index": idx, "value": math.sin(2.0 * math.pi * 50.0 * idx / scenario["sample_rate_hz"])}
        for idx in range(scenario["timeline_len"])
    ]
    scenario["sample_revisions"] = [{"revision_id": "seed", "ops": ops}]
    pack = {"schema_version": 3, "scenarios": [scenario]}
    mutated = json.loads(json.dumps(pack))
    mutated["scenarios"][0]["bands"][0]["weight"] = 2.0
    with tempfile.TemporaryDirectory(prefix="hann_ckpt_stale_") as tmp:
        out_path = Path(tmp) / "report.json"
        ckpt_path = Path(tmp) / "state.json"
        run_cli_report(pack, out_path, ckpt_path)
        prior_report = out_path.read_bytes()
        prior_checkpoint = ckpt_path.read_bytes()
        result = run_cli(mutated, out_path, ckpt_path, check=False)
        assert result.returncode != 0
        assert out_path.read_bytes() == prior_report
        assert ckpt_path.read_bytes() == prior_checkpoint


def test_schema_v2_checkpoint_rejected_leaves_outputs_unchanged(audit_bin: Path) -> None:
    """--checkpoint with a schema-version 2 pack exits non-zero and leaves outputs unchanged."""
    pack = {
        "schema_version": 2,
        "scenarios": [
            {
                "id": "v2_ckpt_reject",
                "sample_rate_hz": 200.0,
                "frame_len": 8,
                "hop_len": 4,
                "detrend": "none",
                "gap_policy": "zero_fill",
                "bands": [{"name": "a", "low_hz": 10.0, "high_hz": 40.0}],
                "samples": [0.0, 0.5, 1.0, 0.5, 0.0, -0.5, -1.0, -0.5] * 2,
            }
        ],
    }
    with tempfile.TemporaryDirectory(prefix="hann_v2_ckpt_") as tmp:
        out_path = Path(tmp) / "report.json"
        ckpt_path = Path(tmp) / "state.json"
        run_cli_report(pack, out_path)
        ckpt_path.write_text(
            json.dumps(
                {
                    "schema_version": 3,
                    "pack_fingerprint": "0" * 64,
                    "completed": [],
                }
            ),
            encoding="utf-8",
        )
        prior_report = out_path.read_bytes()
        prior_checkpoint = ckpt_path.read_bytes()
        result = run_cli(pack, out_path, ckpt_path, check=False)
        assert result.returncode != 0
        assert out_path.read_bytes() == prior_report
        assert ckpt_path.read_bytes() == prior_checkpoint


def test_malformed_pack_leaves_existing_report_and_checkpoint_unchanged(audit_bin: Path) -> None:
    """Malformed packs exit non-zero and leave existing report and checkpoint bytes unchanged."""
    scenario = make_v3_scenario("good_ckpt", timeline_len=24, frame_len=12, hop_len=6, min_frame_quality=0.5)
    ops = [
        {"index": idx, "value": math.sin(2.0 * math.pi * 50.0 * idx / scenario["sample_rate_hz"])}
        for idx in range(scenario["timeline_len"])
    ]
    scenario["sample_revisions"] = [{"revision_id": "seed", "ops": ops}]
    good = {"schema_version": 3, "scenarios": [scenario]}
    bad = {"schema_version": 3, "scenarios": [{"id": "missing_fields"}]}
    with tempfile.TemporaryDirectory(prefix="hann_bad_") as tmp:
        out_path = Path(tmp) / "report.json"
        ckpt_path = Path(tmp) / "state.json"
        run_cli_report(good, out_path, ckpt_path)
        prior_report = out_path.read_bytes()
        prior_checkpoint = ckpt_path.read_bytes()
        result = run_cli(bad, out_path, ckpt_path, check=False)
        assert result.returncode != 0
        assert out_path.read_bytes() == prior_report
        assert ckpt_path.read_bytes() == prior_checkpoint


def test_custom_pack_and_nested_output_path(audit_bin: Path) -> None:
    """CLI accepts arbitrary pack paths and creates nested output directories."""
    pack = {
        "schema_version": 2,
        "scenarios": [
            {
                "id": "custom_path",
                "sample_rate_hz": 200.0,
                "frame_len": 16,
                "hop_len": 8,
                "detrend": "none",
                "gap_policy": "zero_fill",
                "bands": [{"name": "a", "low_hz": 10.0, "high_hz": 40.0}],
                "samples": [math.sin(2.0 * math.pi * 25.0 * i / 200.0) for i in range(32)],
            }
        ],
    }
    expected = reference_report(pack)
    with tempfile.TemporaryDirectory(prefix="hann_custom_") as tmp:
        pack_path = Path(tmp) / "nested" / "input" / "pack.json"
        pack_path.parent.mkdir(parents=True, exist_ok=True)
        pack_path.write_text(json.dumps(pack), encoding="utf-8")
        out_path = Path(tmp) / "deep" / "nested" / "out" / "report.json"
        subprocess.run(
            [str(INSTALLED_BINARY), "--pack", str(pack_path), "--out", str(out_path)],
            check=True,
            timeout=60,
            env=_cli_env(),
        )
        got = json.loads(out_path.read_text(encoding="utf-8"))
    assert_report_matches(got, expected)


def test_digest_changes_when_input_changes(audit_bin: Path) -> None:
    """Digest fields change when input samples change."""
    base_samples = [math.sin(2.0 * math.pi * 30.0 * i / 256.0) for i in range(48)]
    pack_a = {
        "schema_version": 2,
        "scenarios": [
            {
                "id": "digest_a",
                "sample_rate_hz": 256.0,
                "frame_len": 24,
                "hop_len": 12,
                "detrend": "none",
                "gap_policy": "zero_fill",
                "bands": [{"name": "b", "low_hz": 20.0, "high_hz": 40.0}],
                "samples": base_samples,
            }
        ],
    }
    pack_b = json.loads(json.dumps(pack_a))
    pack_b["scenarios"][0]["samples"][10] = base_samples[10] + 0.01
    with tempfile.TemporaryDirectory(prefix="hann_digest_") as tmp:
        report_a = run_cli_report(pack_a, Path(tmp) / "a.json")
        report_b = run_cli_report(pack_b, Path(tmp) / "b.json")
    assert report_a["scenarios"][0]["digest_hex"] != report_b["scenarios"][0]["digest_hex"]
    assert report_a["summary"]["digest_hex"] != report_b["summary"]["digest_hex"]


def test_rebuilt_binary_is_native_executable(audit_bin: Path) -> None:
    """Require a native ELF CLI that does not embed verifier paths or Python hooks."""
    elf_magic = bytes([0x7F, 0x45, 0x4C, 0x46])
    for path in (audit_bin, INSTALLED_BINARY):
        blob = path.read_bytes()
        assert blob[:4] == elf_magic, f"{path} is not a native ELF binary"
        assert not blob.startswith(b"#!"), f"{path} must not be a script wrapper"
        for needle in (b"/tests", b"test_outputs", (b"ref" + b"erence_report")):
            assert needle not in blob, f"{path} must not embed verifier oracle paths"
