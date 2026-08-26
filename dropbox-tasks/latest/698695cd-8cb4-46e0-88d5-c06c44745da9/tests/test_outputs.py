"""Verifier tests for thermal radiometry calibration CLI."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT = Path("/app")
BIN = PROJECT / "bin" / "thermalcal"
DEFAULT_INPUT = PROJECT / "input_data"
DEFAULT_OUTPUT = PROJECT / "output_data"
REPORT = DEFAULT_OUTPUT / "calibration_report.json"
FRAMES_JSONL = DEFAULT_OUTPUT / "intermediate" / "frame_summaries.jsonl"
FITS_JSONL = DEFAULT_OUTPUT / "intermediate" / "session_fits.jsonl"
TF_MODULE = Path("/usr/local/share/calibration_tf")
EXPECTATIONS = Path(__file__).resolve().parent / "expectations_radiometry.py"


def close(a: float, b: float, rtol: float = 0.002, atol: float = 0.05) -> bool:
    return abs(a - b) <= max(atol, rtol * max(abs(a), abs(b), 1.0))


def run_expectations(command: str, *args: str) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [sys.executable, str(EXPECTATIONS), command, *args],
        text=True,
        capture_output=True,
        timeout=300,
        check=False,
    )
    if result.returncode != 0:
        raise AssertionError(
            f"expectations failed: {command} {' '.join(args)}\n"
            f"rc={result.returncode}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
    return result


def run_pipeline(project: Path, input_dir: Path) -> dict:
    result = run_expectations("pipeline", str(project), str(input_dir))
    return json.loads(result.stdout)


def directory_digest(input_dir: Path) -> str:
    return run_expectations("digest", str(input_dir)).stdout.strip()


def build_synthetic_input(template_input: Path, output_input: Path) -> None:
    run_expectations("synth", str(template_input), str(output_input))


def run_checked(cmd: list[str], *, timeout: int = 300) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(cmd, text=True, capture_output=True, timeout=timeout, check=False)
    if result.returncode != 0:
        raise AssertionError(
            f"command failed: {' '.join(cmd)}\nrc={result.returncode}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
    return result


def build_cli() -> None:
    run_checked(["go", "build", "-o", str(BIN), "./cmd/thermalcal"], timeout=180)


def run_cli(input_dir: Path, output_dir: Path) -> None:
    shutil.rmtree(output_dir, ignore_errors=True)
    run_checked([str(BIN), str(input_dir), str(output_dir)], timeout=300)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


@pytest.fixture(scope="module")
def built_and_default_run() -> None:
    build_cli()
    run_cli(DEFAULT_INPUT, DEFAULT_OUTPUT)


def test_task_metadata_and_contract() -> None:
    """Instruction names /app paths and declares the calibration report contract."""
    for candidate in (Path("/instruction.md"), Path("/task/instruction.md"), Path("/tests/../instruction.md")):
        if candidate.exists():
            text = candidate.read_text(encoding="utf-8")
            assert "/app" in text
            assert "calibration report" in text.lower()
            return
    pytest.skip("instruction.md not mounted in this harness layout")


def test_builds_native_go_cli(built_and_default_run: None) -> None:
    """Go build produces the /app/bin/thermalcal executable."""
    assert BIN.is_file(), "thermalcal binary missing after go build"


def test_visible_fixture_report_matches_reference(built_and_default_run: None) -> None:
    """Shipped fixture calibration_report.json matches the independent reference model."""
    expected = run_pipeline(PROJECT, DEFAULT_INPUT)
    report = load_json(REPORT)
    ref = expected["calibration_report.json"]
    assert report["schema_version"] == ref["schema_version"]
    assert report["input_digest"] == ref["input_digest"]
    assert len(report["sessions"]) == len(ref["sessions"])
    for got, want in zip(report["sessions"], ref["sessions"]):
        assert got["session_id"] == want["session_id"]
        for key in (
            "cooling_rate_k",
            "half_life_s",
            "residual_rms_c",
            "start_temperature_c",
            "end_temperature_c",
            "ambient_temperature_c",
        ):
            assert close(got[key], want[key]), f"{got['session_id']} {key}"


def test_intermediate_frame_summaries_match_reference(built_and_default_run: None) -> None:
    """Per-frame JSONL summaries match reference trimmed means and pixel counts."""
    expected = run_pipeline(PROJECT, DEFAULT_INPUT)
    got = load_jsonl(FRAMES_JSONL)
    want = expected["intermediate/frame_summaries.jsonl"]
    assert len(got) == len(want)
    for g, w in zip(got, want):
        assert g["session_id"] == w["session_id"]
        assert g["frame_id"] == w["frame_id"]
        assert close(g["trimmed_mean_c"], w["trimmed_mean_c"])
        assert g["usable_pixels"] == w["usable_pixels"]


def test_session_fits_match_reference(built_and_default_run: None) -> None:
    """Session fit JSONL rows match reference cooling rate and residual metrics."""
    expected = run_pipeline(PROJECT, DEFAULT_INPUT)
    got = load_jsonl(FITS_JSONL)
    want = expected["intermediate/session_fits.jsonl"]
    assert len(got) == len(want)
    for g, w in zip(got, want):
        assert close(g["cooling_rate_k"], w["cooling_rate_k"], rtol=0.01, atol=0.0005)
        assert close(g["half_life_s"], w["half_life_s"], rtol=0.01, atol=0.1)
        assert close(g["residual_rms_c"], w["residual_rms_c"])


def test_runtime_reordered_frames_and_crlf_manifest(built_and_default_run: None) -> None:
    """Manifest row reorder and CRLF endings do not change scientific outputs."""
    tmp_in = Path("/tmp/trc_reorder_in")
    tmp_out = Path("/tmp/trc_reorder_out")
    shutil.copytree(DEFAULT_INPUT, tmp_in, dirs_exist_ok=True)
    manifest_path = tmp_in / "manifest.json"
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    for sess in data["sessions"]:
        sess["frames"] = list(reversed(sess["frames"]))
    manifest_path.write_text(json.dumps(data, indent=2).replace("\n", "\r\n") + "\r\n", encoding="utf-8")
    run_cli(tmp_in, tmp_out)
    expected = run_pipeline(PROJECT, tmp_in)
    report = load_json(tmp_out / "calibration_report.json")
    ref = expected["calibration_report.json"]
    for got, want in zip(report["sessions"], ref["sessions"]):
        assert close(got["cooling_rate_k"], want["cooling_rate_k"], rtol=0.01, atol=0.0005)


def test_runtime_renamed_sessions_and_frame_ids(built_and_default_run: None) -> None:
    """Renamed session and frame identifiers appear dynamically in the report."""
    tmp_in = Path("/tmp/trc_rename_in")
    tmp_out = Path("/tmp/trc_rename_out")
    shutil.copytree(DEFAULT_INPUT, tmp_in, dirs_exist_ok=True)
    data = json.loads((tmp_in / "manifest.json").read_text(encoding="utf-8"))
    mapping = {}
    for i, sess in enumerate(data["sessions"]):
        new_id = f"dyn-session-{i}"
        mapping[sess["session_id"]] = new_id
        sess["session_id"] = new_id
        for j, fr in enumerate(sess["frames"]):
            fr["frame_id"] = f"dyn-frame-{i}-{j}"
    (tmp_in / "manifest.json").write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    run_cli(tmp_in, tmp_out)
    report = load_json(tmp_out / "calibration_report.json")
    ids = {s["session_id"] for s in report["sessions"]}
    assert ids == set(mapping.values())


def test_runtime_changed_terraform_constants(built_and_default_run: None) -> None:
    """Perturbed Terraform constants change outputs and still match the reference model."""
    before_constants = json.loads(
        subprocess.check_output(
            ["terraform", "-chdir=" + str(TF_MODULE), "output", "-json", "calibration_constants"],
            text=True,
        )
    )
    mutated = json.loads(json.dumps(before_constants))
    mutated["cam-ir7"]["gain"] = round(mutated["cam-ir7"]["gain"] + 0.02, 6)
    var_file = TF_MODULE / "override.tfvars.json"
    var_file.write_text(json.dumps({"camera_profiles": mutated}, indent=2) + "\n", encoding="utf-8")
    try:
        run_checked(
            ["terraform", "-chdir=" + str(TF_MODULE), "apply", "-auto-approve", "-input=false", f"-var-file={var_file}"],
            timeout=120,
        )
        after_constants = json.loads(
            subprocess.check_output(
                ["terraform", "-chdir=" + str(TF_MODULE), "output", "-json", "calibration_constants"],
                text=True,
            )
        )
        assert before_constants["cam-ir7"]["gain"] != after_constants["cam-ir7"]["gain"]
        tmp_out = Path("/tmp/trc_tf_out")
        run_cli(DEFAULT_INPUT, tmp_out)
        after_ref = run_pipeline(PROJECT, DEFAULT_INPUT)
        after_go = load_json(tmp_out / "calibration_report.json")
        assert after_go["sessions"]
        assert close(
            after_go["sessions"][0]["cooling_rate_k"],
            after_ref["calibration_report.json"]["sessions"][0]["cooling_rate_k"],
            rtol=0.01,
            atol=0.0005,
        )
    finally:
        var_file.unlink(missing_ok=True)
        run_checked(
            ["terraform", "-chdir=" + str(TF_MODULE), "apply", "-auto-approve", "-input=false"],
            timeout=120,
        )


def test_runtime_generated_synthetic_sessions(built_and_default_run: None) -> None:
    """Runtime synthesized PNG sessions recover plausible cooling curve parameters."""
    tmp_in = Path("/tmp/trc_synth_in")
    tmp_out = Path("/tmp/trc_synth_out")
    build_synthetic_input(DEFAULT_INPUT, tmp_in)
    run_cli(tmp_in, tmp_out)
    expected = run_pipeline(PROJECT, tmp_in)
    report = load_json(tmp_out / "calibration_report.json")
    ref = expected["calibration_report.json"]["sessions"][0]
    s0 = report["sessions"][0]
    assert s0["frame_count"] == ref["frame_count"] == 8
    assert s0["usable_frame_count"] == ref["usable_frame_count"] == 8
    assert close(s0["cooling_rate_k"], ref["cooling_rate_k"], rtol=0.05, atol=0.002)
    assert s0["start_temperature_c"] > s0["end_temperature_c"]


def test_bad_shortcuts_fail(built_and_default_run: None) -> None:
    """Source reads inputs dynamically and does not embed golden report text."""
    src = (PROJECT / "internal/api/api.go").read_text(encoding="utf-8")
    assert "calibration_report" not in src
    assert "/tests" not in src
    assert "/solution" not in src
    assert "input_data" in src or "InputDir" in src
    assert not (PROJECT / "tools" / "lab_png_utils.py").exists()
    assert not (PROJECT / "tools" / "expectations_radiometry.py").exists()


def test_creates_nested_output_directory(built_and_default_run: None) -> None:
    """CLI creates nested intermediate directories under a deep output path."""
    nested = Path("/app/output_data/nested/deep/out")
    run_cli(DEFAULT_INPUT, nested)
    assert (nested / "intermediate/frame_summaries.jsonl").is_file()


def test_deterministic_output_bytes(built_and_default_run: None) -> None:
    """Repeated runs on identical input produce byte-identical output files."""
    out_a = Path("/tmp/trc_det_a")
    out_b = Path("/tmp/trc_det_b")
    run_cli(DEFAULT_INPUT, out_a)
    run_cli(DEFAULT_INPUT, out_b)
    for rel in ("calibration_report.json", "intermediate/frame_summaries.jsonl", "intermediate/session_fits.jsonl"):
        assert (out_a / rel).read_bytes() == (out_b / rel).read_bytes()


def test_no_fixed_golden_replay(built_and_default_run: None) -> None:
    """Report input_digest tracks the input directory rather than a static constant."""
    digest_a = directory_digest(DEFAULT_INPUT)
    tmp_in = Path("/tmp/trc_digest_probe")
    shutil.copytree(DEFAULT_INPUT, tmp_in, dirs_exist_ok=True)
    digest_b = directory_digest(tmp_in)
    assert digest_a == digest_b
    report = load_json(REPORT)
    assert report["input_digest"] == digest_a
