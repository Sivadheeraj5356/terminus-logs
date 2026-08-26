from __future__ import annotations

import functools
import hashlib
import json
import math
import os
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

PUBLIC_INPUT = Path("/app/thermal_problem/cases")
PUBLIC_OUTPUT = Path("/app/thermal_mode_results")
SOURCE = Path("/app/thermal_modes.rs")
BINARY = Path("/app/thermal_modes")
EXPECTED_PUBLIC = {"alloy.json", "basalt.json", "ceramic.json", "glass.json", "graphite.json"}

COPPER_CASE_FILENAME = "coppermesh.case"
COPPER_REPORT_FILENAME = "coppermesh.json"
STONE_REPORT_FILENAME = "stonefoam.json"
PRESERVE_FILENAME = "preserve.me"
PRESERVE_CONTENT = "unchanged"
GUARD_FILENAME = "guard.txt"
GUARD_CONTENT = "guard"
FLOAT_FIELDS = (
    "eigenvalue",
    "left_amplitude",
    "interface1_left",
    "interface1_right",
    "interface2_left",
    "interface2_right",
    "right_amplitude",
    "interface1_flux_left",
    "interface1_flux_right",
    "interface2_flux_left",
    "interface2_flux_right",
    "sensitivity_h_right",
    "sensitivity_R12",
    "modal_heat_content",
)
MODE_FIELDS = ("index", *FLOAT_FIELDS)
INPUT_SHA256 = {
    "alloy.case": "6dc793a569c572847e61bd1c3780dd58e535347ec11d4c6086eaa60b52d89a91",
    "basalt.case": "a6a9ad2a419c2d47cbe9972af5d320d7803a819e459b1af2b8161a2ca526776a",
    "ceramic.case": "7a895e0c81eaa5c931cd27a0471fc22a061610f7dba8144bb1666e30d557b1ad",
    "glass.case": "d7e4e3824a71f24450267cc7d165f3755c07c4fdd52c0f7676e5fe79e50d83ea",
    "graphite.case": "c6883c312cfffeb43ffc180d75205a4414f001ebf5650a5e2c0c2f220241df4c",
}

HIDDEN_CASES = {
    "coppermesh": {
        "name": "coppermesh",
        "modes": 7,
        "mu_max": 95.0,
        "mu_step": 0.0022,
        "L1": 0.36,
        "k1": 44.0,
        "alpha1": 1.72,
        "c1": 0.74,
        "L2": 0.57,
        "k2": 13.0,
        "alpha2": 0.53,
        "c2": 1.42,
        "L3": 0.41,
        "k3": 31.0,
        "alpha3": 1.18,
        "c3": 0.93,
        "R12": 0.024,
        "S12": 0.011,
        "R23": 0.039,
        "S23": 0.016,
        "h_left": 0.92,
        "b_left": 0.021,
        "h_right": 1.48,
        "b_right": 0.034,
    },
    "stonefoam": {
        "name": "stonefoam",
        "modes": 9,
        "mu_max": 85.0,
        "mu_step": 0.0024,
        "L1": 0.48,
        "k1": 3.2,
        "alpha1": 0.21,
        "c1": 2.15,
        "L2": 0.35,
        "k2": 1.1,
        "alpha2": 0.075,
        "c2": 3.05,
        "L3": 0.59,
        "k3": 5.6,
        "alpha3": 0.32,
        "c3": 1.84,
        "R12": 0.095,
        "S12": 0.028,
        "R23": 0.063,
        "S23": 0.024,
        "h_left": 1.25,
        "b_left": 0.046,
        "h_right": 0.58,
        "b_right": 0.027,
    },
}

CLOSE_ROOT_CASE = {
    "name": "nearcluster",
    "modes": 8,
    "mu_max": 7.0,
    "mu_step": 0.02,
    "L1": 1.0,
    "k1": 1.0,
    "alpha1": 1.0,
    "c1": 1.0,
    "L2": 1.0,
    "k2": 1.0,
    "alpha2": 1.0,
    "c2": 1.0,
    "L3": 1.0,
    "k3": 1.0,
    "alpha3": 1.0,
    "c3": 1.0,
    "R12": 200.0,
    "S12": 0.0,
    "R23": 200.0,
    "S23": 0.0,
    "h_left": 0.05,
    "b_left": 0.0,
    "h_right": 0.05,
    "b_right": 0.0,
}


CASE_KEYS = (
    "name",
    "modes",
    "mu_max",
    "mu_step",
    "L1",
    "k1",
    "alpha1",
    "c1",
    "L2",
    "k2",
    "alpha2",
    "c2",
    "L3",
    "k3",
    "alpha3",
    "c3",
    "R12",
    "S12",
    "R23",
    "S23",
    "h_left",
    "b_left",
    "h_right",
    "b_right",
)


def _parse_case(path: Path) -> dict[str, float | int | str]:
    """Parse one supplied case file for verifier-side reference calculations."""
    values: dict[str, float | int | str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        key, value = raw.split("=", 1)
        if key == "name":
            values[key] = value
        elif key == "modes":
            values[key] = int(value)
        else:
            values[key] = float(value)
    return values


def _write_case(path: Path, case: dict[str, float | int | str]) -> None:
    """Write one canonical case fixture in the documented key order."""
    path.write_text("".join(f"{key}={case[key]}\n" for key in CASE_KEYS), encoding="utf-8")


def _propagate(phi: float, flux: float, k: float, alpha: float, length: float, eigenvalue: float) -> tuple[float, float]:
    """Propagate temperature amplitude and flux through one homogeneous layer."""
    omega = math.sqrt(eigenvalue / alpha)
    phase = omega * length
    return (
        math.cos(phase) * phi + math.sin(phase) * flux / (k * omega),
        -k * omega * math.sin(phase) * phi + math.cos(phase) * flux,
    )


def _cross(phi: float, flux: float, resistance: float, sheet_capacity: float, eigenvalue: float) -> tuple[float, float]:
    """Apply one resistive and capacitive interface jump."""
    phi_plus = phi - resistance * flux
    return phi_plus, flux - sheet_capacity * eigenvalue * phi_plus


def _trace(case: dict[str, float | int | str], eigenvalue: float) -> dict[str, tuple[float, float]]:
    """Return all boundary and interface states for one trial eigenvalue."""
    phi, flux = 1.0, float(case["h_left"]) - float(case["b_left"]) * eigenvalue
    trace = {"left": (phi, flux)}
    phi, flux = _propagate(phi, flux, float(case["k1"]), float(case["alpha1"]), float(case["L1"]), eigenvalue)
    trace["interface1_left"] = (phi, flux)
    phi, flux = _cross(phi, flux, float(case["R12"]), float(case["S12"]), eigenvalue)
    trace["interface1_right"] = (phi, flux)
    phi, flux = _propagate(phi, flux, float(case["k2"]), float(case["alpha2"]), float(case["L2"]), eigenvalue)
    trace["interface2_left"] = (phi, flux)
    phi, flux = _cross(phi, flux, float(case["R23"]), float(case["S23"]), eigenvalue)
    trace["interface2_right"] = (phi, flux)
    phi, flux = _propagate(phi, flux, float(case["k3"]), float(case["alpha3"]), float(case["L3"]), eigenvalue)
    trace["right"] = (phi, flux)
    return trace


def _determinant(case: dict[str, float | int | str], eigenvalue: float) -> float:
    """Evaluate the dynamic right-boundary characteristic determinant."""
    phi, flux = _trace(case, eigenvalue)["right"]
    return flux + float(case["h_right"]) * phi - float(case["b_right"]) * eigenvalue * phi


def _refine_reference_root(
    case: dict[str, float | int | str], left: float, right: float, f_left: float
) -> float:
    """Refine one sign-changing bracket in mu with an independent high-precision interval contraction."""
    for _ in range(140):
        middle = (left + right) / 2.0
        f_middle = _determinant(case, middle * middle)
        if (f_left > 0.0) != (f_middle > 0.0):
            right = middle
        else:
            left, f_left = middle, f_middle
    return (left + right) / 2.0


@functools.lru_cache(maxsize=64)
def _roots_cached(case_items: tuple[tuple[str, float | int | str], ...]) -> tuple[float, ...]:
    """Isolate roots on a verifier-only mesh finer than the task's guaranteed minimum separation."""
    case = dict(case_items)
    roots_mu: list[float] = []
    reference_step = min(float(case["mu_step"]) / 128.0, 1.25e-5)
    mu_left = 1.0e-7
    f_left = _determinant(case, mu_left * mu_left)
    assert math.isfinite(f_left)
    while mu_left < float(case["mu_max"]) and len(roots_mu) < int(case["modes"]):
        mu_right = min(float(case["mu_max"]), mu_left + reference_step)
        f_right = _determinant(case, mu_right * mu_right)
        assert math.isfinite(f_right)
        candidate: float | None = None
        if f_left == 0.0:
            candidate = mu_left
        elif f_right == 0.0:
            candidate = mu_right
        elif (f_left > 0.0) != (f_right > 0.0):
            candidate = _refine_reference_root(case, mu_left, mu_right, f_left)
        if candidate is not None and (not roots_mu or abs(candidate - roots_mu[-1]) > 2.5e-8):
            roots_mu.append(candidate)
        mu_left, f_left = mu_right, f_right
    assert len(roots_mu) == int(case["modes"]), (case["name"], roots_mu)
    assert all(right - left >= 9.5e-5 for left, right in zip(roots_mu, roots_mu[1:])), (
        case["name"],
        roots_mu,
    )
    return tuple(mu * mu for mu in roots_mu)


def _roots(case: dict[str, float | int | str]) -> list[float]:
    """Return independently isolated eigenvalues for a validated case."""
    return list(_roots_cached(tuple((key, case[key]) for key in CASE_KEYS)))


def _square_integral(a: float, b: float, omega: float, length: float) -> float:
    """Integrate the square of a local sinusoidal mode exactly."""
    phase = omega * length
    return (
        a * a * (length / 2.0 + math.sin(2.0 * phase) / (4.0 * omega))
        + b * b * (length / 2.0 - math.sin(2.0 * phase) / (4.0 * omega))
        + a * b * math.sin(phase) ** 2 / omega
    )


def _linear_integral(a: float, b: float, omega: float, length: float) -> float:
    """Integrate a local sinusoidal mode exactly."""
    phase = omega * length
    return a * math.sin(phase) / omega + b * (1.0 - math.cos(phase)) / omega


def _expected_mode(case: dict[str, float | int | str], index: int, eigenvalue: float) -> dict[str, float | int]:
    states = _trace(case, eigenvalue)
    omega1 = math.sqrt(eigenvalue / float(case["alpha1"]))
    omega2 = math.sqrt(eigenvalue / float(case["alpha2"]))
    omega3 = math.sqrt(eigenvalue / float(case["alpha3"]))
    b1 = states["left"][1] / (float(case["k1"]) * omega1)
    b2 = states["interface1_right"][1] / (float(case["k2"]) * omega2)
    b3 = states["interface2_right"][1] / (float(case["k3"]) * omega3)
    mass = (
        float(case["c1"]) * _square_integral(states["left"][0], b1, omega1, float(case["L1"]))
        + float(case["c2"]) * _square_integral(states["interface1_right"][0], b2, omega2, float(case["L2"]))
        + float(case["c3"]) * _square_integral(states["interface2_right"][0], b3, omega3, float(case["L3"]))
        + float(case["b_left"]) * states["left"][0] ** 2
        + float(case["b_right"]) * states["right"][0] ** 2
        + float(case["S12"]) * states["interface1_right"][0] ** 2
        + float(case["S23"]) * states["interface2_right"][0] ** 2
    )
    scale = 1.0 / math.sqrt(mass)
    heat = scale * (
        float(case["c1"]) * _linear_integral(states["left"][0], b1, omega1, float(case["L1"]))
        + float(case["c2"]) * _linear_integral(states["interface1_right"][0], b2, omega2, float(case["L2"]))
        + float(case["c3"]) * _linear_integral(states["interface2_right"][0], b3, omega3, float(case["L3"]))
        + float(case["b_left"]) * states["left"][0]
        + float(case["b_right"]) * states["right"][0]
        + float(case["S12"]) * states["interface1_right"][0]
        + float(case["S23"]) * states["interface2_right"][0]
    )
    lambda_step = max(1.0e-6, 1.0e-5 * eigenvalue)
    f_lambda = (
        -_determinant(case, eigenvalue + 2.0 * lambda_step)
        + 8.0 * _determinant(case, eigenvalue + lambda_step)
        - 8.0 * _determinant(case, eigenvalue - lambda_step)
        + _determinant(case, eigenvalue - 2.0 * lambda_step)
    ) / (12.0 * lambda_step)

    def parameter_derivative(key: str, step: float) -> float:
        shifted: list[float] = []
        for multiplier in (2.0, 1.0, -1.0, -2.0):
            variant = dict(case)
            variant[key] = float(case[key]) + multiplier * step
            shifted.append(_determinant(variant, eigenvalue))
        return (-shifted[0] + 8.0 * shifted[1] - 8.0 * shifted[2] + shifted[3]) / (12.0 * step)

    f_h = parameter_derivative("h_right", 1.0e-5)
    f_r = parameter_derivative("R12", 1.0e-6)
    return {
        "index": index,
        "eigenvalue": eigenvalue,
        "left_amplitude": scale,
        "interface1_left": states["interface1_left"][0] * scale,
        "interface1_right": states["interface1_right"][0] * scale,
        "interface2_left": states["interface2_left"][0] * scale,
        "interface2_right": states["interface2_right"][0] * scale,
        "right_amplitude": states["right"][0] * scale,
        "interface1_flux_left": states["interface1_left"][1] * scale,
        "interface1_flux_right": states["interface1_right"][1] * scale,
        "interface2_flux_left": states["interface2_left"][1] * scale,
        "interface2_flux_right": states["interface2_right"][1] * scale,
        "sensitivity_h_right": -f_h / f_lambda,
        "sensitivity_R12": -f_r / f_lambda,
        "modal_heat_content": heat,
    }


def _reference(case: dict[str, float | int | str]) -> dict:
    roots = _roots(case)
    return {
        "case": case["name"],
        "mode_count": case["modes"],
        "modes": [_expected_mode(case, index, root) for index, root in enumerate(roots, 1)],
    }


def _compile(source: Path = SOURCE, binary: Path | None = None) -> Path:
    destination = binary or Path("/tmp/thermal_modes_verifier")
    completed = subprocess.run(
        ["rustc", "--edition=2021", "-O", str(source), "-o", str(destination)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=120,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    return destination


def _run(
    binary: Path,
    input_dir: Path,
    output_dir: Path,
    *,
    expect_success: bool = True,
    description: str = "solver invocation",
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        [str(binary), "--input-dir", str(input_dir), "--output-dir", str(output_dir)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=180,
        check=False,
    )
    if expect_success:
        assert completed.returncode == 0, f"{description} failed: {completed.stderr}"
    else:
        assert completed.returncode != 0, f"{description} unexpectedly succeeded"
    return completed


def _run_arguments_expect_failure(binary: Path, arguments: list[str], description: str) -> None:
    completed = subprocess.run(
        [str(binary), *arguments],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
        check=False,
    )
    assert completed.returncode != 0, f"{description} unexpectedly succeeded"


def _canonical_report(document: dict) -> str:
    """Render the documented two-space JSON layout from already parsed values."""
    lines = [
        "{",
        f'  "case": {json.dumps(document["case"])},',
        f'  "mode_count": {document["mode_count"]},',
        '  "modes": [',
    ]
    for position, mode in enumerate(document["modes"]):
        lines.append("    {")
        lines.append(f'      "index": {mode["index"]},')
        for field_index, field in enumerate(FLOAT_FIELDS):
            comma = "," if field_index + 1 < len(FLOAT_FIELDS) else ""
            lines.append(f'      "{field}": {mode[field]:.10f}{comma}')
        lines.append("    }" + ("," if position + 1 < len(document["modes"]) else ""))
    lines.extend(["  ]", "}"])
    return "\n".join(lines) + "\n"


def _validate_report(path: Path, case: dict[str, float | int | str]) -> dict:
    """Validate schema, canonical whitespace, numeric types, finiteness, and decimal precision."""
    raw = path.read_text(encoding="utf-8")
    assert "\t" not in raw and "\r" not in raw
    assert raw.endswith("\n") and not raw.endswith("\n\n")
    assert all(line and line == line.rstrip() for line in raw.splitlines())
    document = json.loads(raw)
    assert list(document) == ["case", "mode_count", "modes"]
    assert document["case"] == case["name"]
    assert type(document["mode_count"]) is int and document["mode_count"] == case["modes"]
    assert len(document["modes"]) == case["modes"]
    for index, mode in enumerate(document["modes"], 1):
        assert list(mode) == list(MODE_FIELDS)
        assert type(mode["index"]) is int and mode["index"] == index
        for field in FLOAT_FIELDS:
            assert type(mode[field]) is float and math.isfinite(mode[field])
    assert raw == _canonical_report(document)
    return document


def _compare(document: dict, case: dict[str, float | int | str]) -> None:
    expected = _reference(case)
    for actual_mode, expected_mode in zip(document["modes"], expected["modes"]):
        assert actual_mode["index"] == expected_mode["index"]
        for field in FLOAT_FIELDS:
            actual = actual_mode[field]
            expected_value = expected_mode[field]
            if field == "sensitivity_h_right":
                assert math.isclose(actual, expected_value, rel_tol=5.0e-7, abs_tol=5.0e-7), (
                    case["name"], actual_mode["index"], field, actual, expected_value
                )
            elif field == "sensitivity_R12":
                assert math.isclose(actual, expected_value, rel_tol=5.0e-7, abs_tol=5.0e-7), (
                    case["name"], actual_mode["index"], field, actual, expected_value
                )
            else:
                assert abs(actual - expected_value) <= 8.0e-9, (
                    case["name"], actual_mode["index"], field, actual, expected_value
                )
        assert abs(_determinant(case, actual_mode["eigenvalue"])) <= 1.0e-6
    eigenvalues = [mode["eigenvalue"] for mode in document["modes"]]
    assert all(left < right for left, right in zip(eigenvalues, eigenvalues[1:]))


def _check_supplied_cases_are_immutable() -> None:
    """The five public scientific case files retain their exact supplied bytes."""
    assert {path.name for path in PUBLIC_INPUT.glob("*.case")} == set(INPUT_SHA256)
    for name, digest in INPUT_SHA256.items():
        assert hashlib.sha256((PUBLIC_INPUT / name).read_bytes()).hexdigest() == digest


def _check_required_rust_source_binary_and_public_reports_exist() -> None:
    """The standalone Rust source, executable, and exact public result set are present."""
    assert SOURCE.is_file() and not SOURCE.is_symlink()
    assert BINARY.is_file() and os.access(BINARY, os.X_OK) and not BINARY.is_symlink()
    assert PUBLIC_OUTPUT.is_dir()
    assert {entry.name for entry in PUBLIC_OUTPUT.iterdir()} == EXPECTED_PUBLIC
    assert all(entry.is_file() and not entry.is_symlink() for entry in PUBLIC_OUTPUT.iterdir())


def _check_public_reports_match_independent_multilayer_reference() -> None:
    """All public reports match independent roots, contact jumps, normalization, heat content, and sensitivities."""
    for path in sorted(PUBLIC_INPUT.glob("*.case")):
        case = _parse_case(path)
        document = _validate_report(PUBLIC_OUTPUT / f"{case['name']}.json", case)
        _compare(document, case)


def _check_rust_source_recompiles_and_generalizes_to_held_out_cases() -> None:
    """The submitted Rust source compiles cleanly and solves unseen valid three-layer cases."""
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        binary = _compile(binary=root / "thermal_modes")
        input_dir, output_dir = root / "cases", root / "results"
        input_dir.mkdir()
        for name, case in HIDDEN_CASES.items():
            _write_case(input_dir / f"{name}.case", case)
        _run(binary, input_dir, output_dir)
        assert {path.name for path in output_dir.iterdir()} == {f"{name}.json" for name in HIDDEN_CASES}
        for name, case in HIDDEN_CASES.items():
            document = _validate_report(output_dir / f"{name}.json", case)
            _compare(document, case)


def _check_close_eigenvalue_clusters_are_isolated_without_skips() -> None:
    """A coarse mu_step does not hide multiple tightly clustered positive eigenvalues."""
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        binary = _compile(binary=root / "thermal_modes")
        input_dir, output_dir = root / "cases", root / "results"
        input_dir.mkdir()
        _write_case(input_dir / "nearcluster.case", CLOSE_ROOT_CASE)
        _run(binary, input_dir, output_dir, description="close-root cluster")
        document = _validate_report(output_dir / "nearcluster.json", CLOSE_ROOT_CASE)
        _compare(document, CLOSE_ROOT_CASE)
        mu_values = [math.sqrt(mode["eigenvalue"]) for mode in document["modes"]]
        gaps = [right - left for left, right in zip(mu_values, mu_values[1:])]
        assert min(gaps) < 2.0e-4
        assert min(gaps) >= 9.5e-5

        coarse_step = float(CLOSE_ROOT_CASE["mu_step"])
        coarse_start = 1.0e-7
        buckets: dict[int, list[float]] = {}
        for mu_value in mu_values:
            bucket = math.floor((mu_value - coarse_start) / coarse_step)
            buckets.setdefault(bucket, []).append(mu_value)
        clustered_bucket = next(bucket for bucket, values in buckets.items() if len(values) >= 2)
        left_mu = coarse_start + clustered_bucket * coarse_step
        right_mu = left_mu + coarse_step
        left_value = _determinant(CLOSE_ROOT_CASE, left_mu * left_mu)
        right_value = _determinant(CLOSE_ROOT_CASE, right_mu * right_mu)
        assert (left_value > 0.0) == (right_value > 0.0)


def _check_cli_path_and_schema_failures_are_nonzero() -> None:
    """Documented CLI, path-separation, schema, name, and root-domain failures preserve output and return non-zero."""
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        binary = _compile(binary=root / "thermal_modes")

        cli_failures = (
            ([], "no arguments"),
            (["--input-dir"], "missing input-dir value"),
            (["--output-dir"], "missing output-dir value"),
            (["--input-dir", "a"], "missing output-dir argument"),
            (["--output-dir", "b"], "missing input-dir argument"),
            (["--unknown", "x"], "unknown flag"),
            (["--input-dir", "a", "--input-dir", "b", "--output-dir", "c"], "duplicate input-dir"),
            (["--input-dir", "a", "--output-dir", "b", "--output-dir", "c"], "duplicate output-dir"),
        )
        for arguments, description in cli_failures:
            _run_arguments_expect_failure(binary, list(arguments), description)

        missing_input = root / "missing-input"
        _run(binary, missing_input, root / "missing-output", expect_success=False, description="nonexistent input directory")

        empty_input = root / "empty-input"
        empty_input.mkdir()
        _run(binary, empty_input, root / "empty-output", expect_success=False, description="empty input directory")

        valid_case = dict(HIDDEN_CASES["coppermesh"])
        overlap_input = root / "overlap-input"
        overlap_input.mkdir()
        _write_case(overlap_input / COPPER_CASE_FILENAME, valid_case)
        original_bytes = (overlap_input / COPPER_CASE_FILENAME).read_bytes()
        _run(binary, overlap_input, overlap_input, expect_success=False, description="identical input and output paths")
        assert (overlap_input / COPPER_CASE_FILENAME).read_bytes() == original_bytes

        ancestor_root = root / "ancestor-root"
        ancestor_input = ancestor_root / "cases"
        ancestor_input.mkdir(parents=True)
        _write_case(ancestor_input / COPPER_CASE_FILENAME, valid_case)
        _run(binary, ancestor_input, ancestor_root, expect_success=False, description="output path containing input directory")
        assert (ancestor_input / COPPER_CASE_FILENAME).is_file()

        child_output = overlap_input / "generated-reports"
        _run(binary, overlap_input, child_output, expect_success=False, description="output directory inside input directory")
        with pytest.raises(FileNotFoundError):
            child_output.lstat()
        assert (overlap_input / COPPER_CASE_FILENAME).read_bytes() == original_bytes

        def expect_case_failure(label: str, files: dict[str, str | bytes]) -> None:
            input_dir = root / f"invalid-{label}"
            output_dir = root / f"invalid-{label}-output"
            input_dir.mkdir()
            output_dir.mkdir()
            marker = output_dir / PRESERVE_FILENAME
            marker.write_text(PRESERVE_CONTENT, encoding="utf-8")
            for filename, content in files.items():
                path = input_dir / filename
                if isinstance(content, bytes):
                    path.write_bytes(content)
                else:
                    path.write_text(content, encoding="utf-8")
            _run(binary, input_dir, output_dir, expect_success=False, description=label)
            assert marker.read_text(encoding="utf-8") == PRESERVE_CONTENT, label
            assert {entry.name for entry in output_dir.iterdir()} == {PRESERVE_FILENAME}, label

        valid_text = "".join(f"{key}={valid_case[key]}\n" for key in CASE_KEYS)
        expect_case_failure("malformed-key-value", {"bad.case": valid_text.replace("L1=0.36\n", "not-a-key-value\n")})
        expect_case_failure("repeated-equals", {"bad.case": valid_text.replace("L1=0.36", "L1=0.36=extra")})
        expect_case_failure("empty-key", {"bad.case": valid_text.replace("L1=0.36", "=0.36")})
        expect_case_failure("empty-value", {"bad.case": valid_text.replace("L1=0.36", "L1=")})
        expect_case_failure("comment-line", {"bad.case": "# comment\n" + valid_text})
        expect_case_failure("duplicate-key", {"bad.case": valid_text + "L1=0.99\n"})
        expect_case_failure(
            "missing-key",
            {"bad.case": "".join(f"{key}={valid_case[key]}\n" for key in CASE_KEYS if key != "L1")},
        )
        expect_case_failure("extra-key", {"bad.case": valid_text + "unexpected=1\n"})
        expect_case_failure("invalid-name-slash", {"bad.case": valid_text.replace("name=coppermesh", "name=bad/name")})
        expect_case_failure("invalid-name-unicode", {"bad.case": valid_text.replace("name=coppermesh", "name=café")})
        expect_case_failure("invalid-name-empty", {"bad.case": valid_text.replace("name=coppermesh", "name=")})
        expect_case_failure("invalid-utf8", {"bad.case": valid_text.encode("utf-8") + b"\xff"})

        duplicate_name_a = dict(valid_case)
        duplicate_name_b = dict(HIDDEN_CASES["stonefoam"])
        duplicate_name_b["name"] = duplicate_name_a["name"]
        expect_case_failure(
            "duplicate-case-name",
            {
                "first.case": "".join(f"{key}={duplicate_name_a[key]}\n" for key in CASE_KEYS),
                "second.case": "".join(f"{key}={duplicate_name_b[key]}\n" for key in CASE_KEYS),
            },
        )

        short_case = dict(valid_case)
        short_case["mu_max"] = 0.01
        expect_case_failure(
            "insufficient-root-domain",
            {"short.case": "".join(f"{key}={short_case[key]}\n" for key in CASE_KEYS)},
        )


def _check_whitespace_and_numeric_validation_is_complete() -> None:
    """Whitespace variants and every documented numeric class are accepted or rejected exactly as specified."""
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        binary = _compile(binary=root / "thermal_modes")
        valid_case = dict(HIDDEN_CASES["coppermesh"])

        def text_with_value(key: str, value: str) -> str:
            return "".join(f"{candidate}={value if candidate == key else valid_case[candidate]}\n" for candidate in CASE_KEYS)

        def expect_failure(label: str, content: str | bytes) -> None:
            input_dir = root / f"invalid-{label}"
            output_dir = root / f"invalid-{label}-output"
            input_dir.mkdir()
            output_dir.mkdir()
            marker = output_dir / PRESERVE_FILENAME
            marker.write_text(PRESERVE_CONTENT, encoding="utf-8")
            path = input_dir / "bad.case"
            if isinstance(content, bytes):
                path.write_bytes(content)
            else:
                path.write_text(content, encoding="utf-8")
            _run(binary, input_dir, output_dir, expect_success=False, description=label)
            assert marker.read_text(encoding="utf-8") == PRESERVE_CONTENT
            assert {entry.name for entry in output_dir.iterdir()} == {PRESERVE_FILENAME}

        valid_text = "".join(f"{key}={valid_case[key]}\n" for key in CASE_KEYS)
        whitespace_failures = {
            "blank-first-line": "\n" + valid_text,
            "blank-middle-line": valid_text.replace("L2=0.57\n", "L2=0.57\n\n"),
            "blank-last-line": valid_text + "\n",
            "space-before-key": valid_text.replace("L1=0.36", " L1=0.36"),
            "space-after-key": valid_text.replace("L1=0.36", "L1 =0.36"),
            "space-before-value": valid_text.replace("L1=0.36", "L1= 0.36"),
            "space-after-value": valid_text.replace("L1=0.36", "L1=0.36 "),
            "tab-before-key": valid_text.replace("L1=0.36", "\tL1=0.36"),
            "tab-after-key": valid_text.replace("L1=0.36", "L1\t=0.36"),
            "tab-before-value": valid_text.replace("L1=0.36", "L1=\t0.36"),
            "tab-after-value": valid_text.replace("L1=0.36", "L1=0.36\t"),
            "whitespace-only-line": valid_text.replace("L2=0.57\n", "L2=0.57\n \t\n"),
            "embedded-nul": valid_text.replace("L1=0.36", "L1=0.\x0036"),
        }
        for label, content in whitespace_failures.items():
            expect_failure(label, content)

        float_keys = tuple(key for key in CASE_KEYS if key not in {"name", "modes"})
        positive_keys = (
            "mu_max", "mu_step", "L1", "k1", "alpha1", "c1", "L2", "k2", "alpha2", "c2",
            "L3", "k3", "alpha3", "c3",
        )
        nonnegative_keys = ("R12", "S12", "R23", "S23", "h_left", "b_left", "h_right", "b_right")

        for key in float_keys:
            for label_value, value in (
                ("not-number", "not-a-number"),
                ("nan", "NaN"),
                ("positive-infinity", "inf"),
                ("negative-infinity", "-inf"),
                ("overflow", "1e309"),
            ):
                expect_failure(f"{key}-{label_value}", text_with_value(key, value))

        for key in positive_keys:
            expect_failure(f"{key}-zero", text_with_value(key, "0"))
            expect_failure(f"{key}-negative", text_with_value(key, "-1e-6"))
            expect_failure(f"{key}-underflow", text_with_value(key, "1e-400"))

        for key in nonnegative_keys:
            expect_failure(f"{key}-negative", text_with_value(key, "-1e-6"))

        for label, value in (
            ("modes-zero", "0"),
            ("modes-negative", "-1"),
            ("modes-above-range", "21"),
            ("modes-fractional", "7.5"),
            ("modes-nan", "NaN"),
            ("modes-overflow", "999999999999999999999999999999999"),
        ):
            expect_failure(label, text_with_value("modes", value))

        expect_failure("mu-step-equals-max", text_with_value("mu_step", str(valid_case["mu_max"])))
        expect_failure("mu-step-above-max", text_with_value("mu_step", "96"))
        expect_failure("mu-step-over-cap", text_with_value("mu_step", "0.0200001"))

        # CRLF is a line-ending convention rather than horizontal field whitespace.
        crlf_input = root / "crlf-input"
        crlf_output = root / "crlf-output"
        crlf_input.mkdir()
        (crlf_input / COPPER_CASE_FILENAME).write_bytes(valid_text.replace("\n", "\r\n").encode("utf-8"))
        _run(binary, crlf_input, crlf_output, description="CRLF valid case")
        _compare(_validate_report(crlf_output / COPPER_REPORT_FILENAME, valid_case), valid_case)

        # Scientific notation is explicitly valid for finite numeric fields.
        scientific_input = root / "scientific-input"
        scientific_output = root / "scientific-output"
        scientific_input.mkdir()
        scientific_lines = []
        for key in CASE_KEYS:
            value = valid_case[key]
            if key in {"name", "modes"}:
                scientific_lines.append(f"{key}={value}\n")
            else:
                scientific_lines.append(f"{key}={float(value):.12e}\n")
        (scientific_input / COPPER_CASE_FILENAME).write_text("".join(scientific_lines), encoding="utf-8")
        _run(binary, scientific_input, scientific_output, description="scientific notation valid case")
        _compare(_validate_report(scientific_output / COPPER_REPORT_FILENAME, valid_case), valid_case)


def _check_restartability_determinism_and_parallel_isolation() -> None:
    """Output paths are removed and recreated; repeated and concurrent runs stay deterministic and isolated."""
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        binary = _compile(binary=root / "thermal_modes")
        input_a, input_b = root / "input-a", root / "input-b"
        input_a.mkdir()
        input_b.mkdir()
        _write_case(input_a / COPPER_CASE_FILENAME, HIDDEN_CASES["coppermesh"])
        _write_case(input_b / "stonefoam.case", HIDDEN_CASES["stonefoam"])

        output_a = root / "output-a"
        output_a.mkdir()
        (output_a / "stale.txt").write_text("stale", encoding="utf-8")
        (output_a / "stale-dir").mkdir()
        (output_a / "stale-dir" / "nested.txt").write_text("nested", encoding="utf-8")

        sentinel = root / "sentinel-target"
        sentinel.mkdir()
        (sentinel / GUARD_FILENAME).write_text(GUARD_CONTENT, encoding="utf-8")
        output_b = root / "output-b"
        output_b.symlink_to(sentinel, target_is_directory=True)

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [
                pool.submit(_run, binary, input_a, output_a, description="parallel output-a"),
                pool.submit(_run, binary, input_b, output_b, description="parallel output-b"),
            ]
            for future in futures:
                future.result()

        assert output_a.is_dir() and not output_a.is_symlink()
        assert output_b.is_dir() and not output_b.is_symlink()
        assert (sentinel / GUARD_FILENAME).read_text(encoding="utf-8") == GUARD_CONTENT
        assert {path.name for path in output_a.iterdir()} == {COPPER_REPORT_FILENAME}
        assert {path.name for path in output_b.iterdir()} == {STONE_REPORT_FILENAME}

        first_a = (output_a / COPPER_REPORT_FILENAME).read_bytes()
        first_b = (output_b / STONE_REPORT_FILENAME).read_bytes()
        (output_a / "stale-again.txt").write_text("stale", encoding="utf-8")
        (output_b / "stale-again").mkdir()
        _run(binary, input_a, output_a, description="restart output-a")
        _run(binary, input_b, output_b, description="restart output-b")
        assert (output_a / COPPER_REPORT_FILENAME).read_bytes() == first_a
        assert (output_b / STONE_REPORT_FILENAME).read_bytes() == first_b
        assert {path.name for path in output_a.iterdir()} == {COPPER_REPORT_FILENAME}
        assert {path.name for path in output_b.iterdir()} == {STONE_REPORT_FILENAME}

        output_file = root / "output-file"
        output_file.write_text("replace me", encoding="utf-8")
        _run(binary, input_a, output_file, description="existing output file replacement")
        assert output_file.is_dir() and not output_file.is_symlink()
        assert {path.name for path in output_file.iterdir()} == {COPPER_REPORT_FILENAME}

        nested_output = root / "new-parent" / "deep" / "output"
        _run(binary, input_a, nested_output, description="nested output directory creation")
        assert nested_output.is_dir() and not nested_output.is_symlink()
        assert {path.name for path in nested_output.iterdir()} == {COPPER_REPORT_FILENAME}

def test_supplied_cases_are_immutable() -> None:
    """The five public scientific case files retain their exact supplied bytes."""
    _check_supplied_cases_are_immutable()


def test_required_rust_source_binary_and_public_reports_exist() -> None:
    """The standalone Rust source, executable, and exact public result set are present."""
    _check_required_rust_source_binary_and_public_reports_exist()


def test_public_reports_match_independent_multilayer_reference() -> None:
    """All public reports match the independent multilayer numerical reference."""
    _check_public_reports_match_independent_multilayer_reference()


def test_rust_source_recompiles_and_generalizes_to_held_out_cases() -> None:
    """The Rust source recompiles and solves additional valid three-layer cases."""
    _check_rust_source_recompiles_and_generalizes_to_held_out_cases()


def test_close_eigenvalue_clusters_are_isolated_without_skips() -> None:
    """Closely spaced positive eigenvalues are isolated without skipped modes."""
    _check_close_eigenvalue_clusters_are_isolated_without_skips()


def test_cli_path_and_schema_failures_are_nonzero() -> None:
    """All documented CLI, path, schema, and search-domain failures return non-zero."""
    _check_cli_path_and_schema_failures_are_nonzero()


def test_whitespace_and_numeric_validation_is_complete() -> None:
    """Whitespace and every documented numerical validation class follow the contract."""
    _check_whitespace_and_numeric_validation_is_complete()


def test_restartability_determinism_and_parallel_isolation() -> None:
    """Output replacement, nested paths, determinism, and parallel isolation are correct."""
    _check_restartability_determinism_and_parallel_isolation()

