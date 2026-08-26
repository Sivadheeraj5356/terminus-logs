"""Candidate-facing verifier — exactly 26 domain tests for the lunar solver."""

from __future__ import annotations

import json
import math
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence, Tuple

import numpy as np

from fixture_tools import (
    FixturePaths,
    clear_inversions,
    configure_micro_case,
    copy_fixture_tree,
    mutate_all_materials,
    read_csv,
    scale_band_responses,
    set_eclipse_point,
    set_illumination_field,
    set_material_field,
    update_solver_config,
    write_depth_grid,
    write_eclipse_profiles,
    write_forcing_intervals,
    write_illumination_cases,
    write_inversion_queries,
    write_observation_queries,
    write_radiometer_bands,
    write_uniform_depth_grid,
)
from reference_model import (
    absorbed_solar_flux,
    band_radiance,
    brightness_temperature,
    build_report,
    cell_conductivity,
    cell_energy,
    compute_brightness_targets,
    eclipse_transmission_at_time,
    heat_capacity,
    load_solver_data,
)


def resolve_candidate_bin() -> Path:
    """Locate the candidate release binary via env override or /app default."""
    for key in ("CANDIDATE_BIN", "LUNAR_REGOLITH_SOLVER_BIN"):
        value = os.environ.get(key)
        if value:
            path = Path(value)
            if path.is_file():
                return path
    fallback = Path("/app/target/release/lunar-regolith-solver")
    if fallback.is_file():
        return fallback
    raise FileNotFoundError(
        "Candidate binary not found; set CANDIDATE_BIN or LUNAR_REGOLITH_SOLVER_BIN"
    )


def run_candidate(
    data_dir: Path,
    output_path: Path,
) -> subprocess.CompletedProcess[str]:
    """Invoke the candidate solver against data_dir writing output_path."""
    binary = resolve_candidate_bin()
    if output_path.exists():
        output_path.unlink()
    for leftover in (
        output_path.with_suffix(".tmp"),
        Path(str(output_path) + ".tmp"),
    ):
        if leftover.exists():
            leftover.unlink()
    return subprocess.run(
        [
            str(binary),
            "--data-dir",
            str(data_dir),
            "--output",
            str(output_path),
        ],
        capture_output=True,
        text=True,
    )


def assert_finite_number(value: Any, label: str) -> float:
    number = float(value)
    assert math.isfinite(number), f"{label} is not finite: {value!r}"
    return number


def assert_no_nan_inf(payload: Any, path: str = "$") -> None:
    if isinstance(payload, dict):
        for key, value in payload.items():
            assert_no_nan_inf(value, f"{path}.{key}")
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            assert_no_nan_inf(value, f"{path}[{index}]")
    elif isinstance(payload, float):
        assert math.isfinite(payload), f"non-finite float at {path}"
    elif isinstance(payload, (int, bool, str)) or payload is None:
        return
    else:
        # JSON numbers may arrive as ints already checked above.
        return


def index_unique(
    rows: Sequence[Mapping[str, Any]],
    key_fn,
) -> Dict[Any, Mapping[str, Any]]:
    """Index rows by key_fn, asserting each key appears once."""
    indexed: Dict[Any, Mapping[str, Any]] = {}
    for row in rows:
        key = key_fn(row)
        assert key not in indexed, f"duplicate row key {key!r}"
        indexed[key] = row
    return indexed


def assert_same_keys(
    actual: Mapping[Any, Any],
    expected: Mapping[Any, Any],
    *,
    label: str,
) -> None:
    missing = set(expected) - set(actual)
    extra = set(actual) - set(expected)
    assert not missing, f"{label}: missing keys {sorted(missing)!r}"
    assert not extra, f"{label}: extra keys {sorted(extra)!r}"


def assert_close(
    actual: float,
    expected: float,
    *,
    abs_tol: float,
    rel_tol: float = 0.0,
    label: str = "value",
) -> None:
    actual_f = assert_finite_number(actual, label)
    expected_f = assert_finite_number(expected, f"expected {label}")
    limit = max(abs_tol, rel_tol * max(abs(expected_f), 1.0))
    assert abs(actual_f - expected_f) <= limit, (
        f"{label}: {actual_f} vs {expected_f} (tol={limit})"
    )


def expect_success(paths: FixturePaths, output_path: Path) -> Dict[str, Any]:
    """Run candidate, assert exit 0, return parsed JSON report."""
    proc = run_candidate(paths.data_dir, output_path)
    assert proc.returncode == 0, (
        f"solver failed\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
    )
    assert output_path.is_file(), "expected report.json to exist"
    report = json.loads(output_path.read_text(encoding="utf-8"))
    assert isinstance(report, dict)
    assert_no_nan_inf(report)
    return report


def expect_failure(paths: FixturePaths, output_path: Path) -> subprocess.CompletedProcess[str]:
    """Run candidate expecting nonzero exit and removal of any stale output."""
    # Plant a stale final report that must be removed on failure.
    output_path.write_text('{"stale": true}\n', encoding="utf-8")
    proc = run_candidate(paths.data_dir, output_path)
    assert proc.returncode != 0, "expected nonzero exit on fatal condition"
    assert proc.stderr.strip(), "expected nonempty stderr diagnostics"
    assert not output_path.exists(), "final report must not remain after failure"
    for leftover in (
        output_path.with_suffix(".tmp"),
        Path(str(output_path) + ".tmp"),
    ):
        assert not leftover.exists(), f"leftover temporary file {leftover}"
    return proc


def temperature_map(
    report: Mapping[str, Any],
) -> Dict[Tuple[str, str, int], float]:
    rows = report["temperature_rows"]
    indexed = index_unique(
        rows,
        lambda row: (row["case_id"], row["observation_id"], int(row["cell_index"])),
    )
    return {key: float(row["temperature_k"]) for key, row in indexed.items()}


def radiometer_map(
    report: Mapping[str, Any],
) -> Dict[str, Mapping[str, Any]]:
    return index_unique(report["radiometer_rows"], lambda row: row["observation_id"])


def flux_rows_for_case(
    report: Mapping[str, Any],
    case_id: str,
) -> List[Mapping[str, Any]]:
    return [row for row in report["surface_flux_rows"] if row["case_id"] == case_id]


def diagnostics_for_case(
    report: Mapping[str, Any],
    case_id: str,
) -> Mapping[str, Any]:
    matches = [row for row in report["solver_diagnostics"] if row["case_id"] == case_id]
    assert len(matches) == 1
    return matches[0]


def independent_insulated_backward_euler(
    thicknesses: Sequence[float],
    temperatures: Sequence[float],
    *,
    density: float,
    heat_capacity: float,
    conductivity: float,
    dt: float,
    steps: int,
) -> np.ndarray:
    """Independent constant-property insulated 1D backward-Euler step chain."""
    count = len(temperatures)
    centers = np.cumsum(thicknesses) - 0.5 * np.asarray(thicknesses, dtype=float)
    state = np.asarray(temperatures, dtype=float).copy()
    capacity = density * heat_capacity * np.asarray(thicknesses, dtype=float)

    for _ in range(steps):
        matrix = np.zeros((count, count), dtype=float)
        rhs = capacity * state / dt
        for index in range(count):
            matrix[index, index] += capacity[index] / dt
            if index > 0:
                gap = centers[index] - centers[index - 1]
                conductance = conductivity / gap
                matrix[index, index] += conductance
                matrix[index, index - 1] -= conductance
                matrix[index - 1, index] -= conductance
                matrix[index - 1, index - 1] += conductance
        state = np.linalg.solve(matrix, rhs)
    return state


def _constant_material_overrides(**extra: Any) -> Dict[str, Any]:
    base = {
        "heat_capacity_c1_j_kg_k2": 0.0,
        "heat_capacity_c2_j_kg_k3": 0.0,
        "conductivity_depth_gradient_per_m": 0.0,
        "radiative_conductivity_w_m_k4": 0.0,
        "surface_emissivity": 0.0,
        "surface_albedo": 0.0,
    }
    base.update(extra)
    return base


# ---------------------------------------------------------------------------
# Thermal tests
# ---------------------------------------------------------------------------


def test_01_uniform_insulated_profile(tmp_path: Path) -> None:
    """Uniform insulated column with zero solar/radiation/geothermal stays invariant."""
    paths = copy_fixture_tree(tmp_path)
    configure_micro_case(
        paths,
        case_id="case_insulated",
        period_s=400.0,
        time_step_s=100.0,
        solar_flux_w_m2=0.0,
        geothermal_flux_w_m2=0.0,
        cell_count=4,
        thickness_m=0.08,
        initial_temperature_k=215.0,
        maximum_spinup_cycles=3,
        spinup_tolerance_k=1.0e-6,
        material_overrides=_constant_material_overrides(),
    )
    report = expect_success(paths, tmp_path / "report.json")
    ref = build_report(paths.data_dir)
    diag = [row for row in report["solver_diagnostics"] if row["case_id"] == "case_insulated"][0]
    assert int(diag["spinup_cycles"]) == 1
    assert_close(
        float(diag["final_spinup_difference_k"]),
        0.0,
        abs_tol=1.0e-12,
        label="spinup delta",
    )
    got = temperature_map(report)
    exp = temperature_map(ref)
    assert_same_keys(got, exp, label="temperature keys")
    for key, expected in exp.items():
        assert_close(got[key], expected, abs_tol=1.0e-6, label=f"T{key}")
        assert_close(got[key], 215.0, abs_tol=1.0e-5, label=f"invariant{key}")
    for row in flux_rows_for_case(report, "case_insulated"):
        assert_close(
            float(row["absorbed_solar_flux_w_m2"]),
            0.0,
            abs_tol=1.0e-12,
            label="absorbed",
        )
        assert_close(
            float(row["emitted_thermal_flux_w_m2"]),
            0.0,
            abs_tol=1.0e-12,
            label="emitted",
        )


def test_02_geothermal_flux(tmp_path: Path) -> None:
    """One-cell Neumann basal heating matches the public analytic identity."""
    paths = copy_fixture_tree(tmp_path)
    period_s = 400.0
    time_step_s = 100.0
    geothermal = 2.0
    density = 1000.0
    heat_capacity = 500.0
    thickness = 0.2
    t0 = 180.0
    configure_micro_case(
        paths,
        case_id="case_geo",
        period_s=period_s,
        time_step_s=time_step_s,
        solar_flux_w_m2=0.0,
        geothermal_flux_w_m2=geothermal,
        cell_count=1,
        thickness_m=thickness,
        initial_temperature_k=t0,
        maximum_spinup_cycles=1,
        spinup_tolerance_k=1.0e6,
        material_overrides=_constant_material_overrides(
            contact_conductivity_w_m_k=0.05,
            heat_capacity_c0_j_kg_k=heat_capacity,
            density_kg_m3=density,
        ),
    )
    report = expect_success(paths, tmp_path / "report.json")
    steps_per_period = int(round(period_s / time_step_s))
    # One unrecorded spin-up period + one report period (maximum_spinup_cycles=1).
    total_steps = 2 * steps_per_period
    analytic = t0 + total_steps * geothermal * time_step_s / (
        density * heat_capacity * thickness
    )
    got = temperature_map(report)
    assert len(got) == 1
    measured = next(iter(got.values()))
    assert_close(measured, analytic, abs_tol=1.0e-6, label="geo analytic T")
    assert measured > t0 + 0.01
    ref = build_report(paths.data_dir)
    assert_close(
        measured,
        next(iter(temperature_map(ref).values())),
        abs_tol=1.0e-6,
        label="geo ref T",
    )
    for row in flux_rows_for_case(report, "case_geo"):
        assert float(row["geothermal_flux_up_w_m2"]) > 0.0
        assert_close(
            float(row["geothermal_flux_up_w_m2"]),
            geothermal,
            abs_tol=1.0e-12,
            label="geo flux",
        )


def test_03_constant_conductivity_relaxation(tmp_path: Path) -> None:
    """Insulated constant-k relaxation matches an independent backward-Euler solve."""
    paths = copy_fixture_tree(tmp_path)
    temps0 = [260.0, 220.0, 190.0, 170.0]
    thickness = 0.12
    dt = 120.0
    period = 480.0
    configure_micro_case(
        paths,
        case_id="case_relax",
        period_s=period,
        time_step_s=dt,
        solar_flux_w_m2=0.0,
        geothermal_flux_w_m2=0.0,
        cell_count=4,
        thickness_m=thickness,
        initial_temperature_k=temps0,
        maximum_spinup_cycles=1,
        spinup_tolerance_k=1.0e6,
        material_overrides=_constant_material_overrides(
            density_kg_m3=1500.0,
            heat_capacity_c0_j_kg_k=700.0,
            contact_conductivity_w_m_k=0.04,
        ),
    )
    report = expect_success(paths, tmp_path / "report.json")
    data = load_solver_data(paths.data_dir)
    material = data.materials["lunar_regolith"]
    steps = int(round(period / dt))
    independent = independent_insulated_backward_euler(
        [thickness] * 4,
        temps0,
        density=material.density_kg_m3,
        heat_capacity=material.heat_capacity_c0_j_kg_k,
        conductivity=material.contact_conductivity_w_m_k,
        dt=dt,
        steps=steps * 2,  # spin-up cycle + report cycle under max_cycles=1 path...
    )
    # With maximum_spinup_cycles=1 the model always runs one unrecorded spin-up
    # period then one recorded period, matching 2 * steps above.
    got = temperature_map(report)
    obs_id = next(iter({key[1] for key in got}))
    for cell_index, expected in enumerate(independent):
        assert_close(
            got[("case_relax", obs_id, cell_index)],
            float(expected),
            abs_tol=5.0e-3,
            label=f"relax cell {cell_index}",
        )
    assert max(got.values()) < max(temps0)
    assert min(got.values()) > min(temps0)


def test_04_temperature_dependent_heat_capacity(tmp_path: Path) -> None:
    """Mutated c1/c2 coefficients change stored enthalpy relative to constant-c0."""
    paths = copy_fixture_tree(tmp_path)
    configure_micro_case(
        paths,
        case_id="case_cp",
        period_s=600.0,
        time_step_s=100.0,
        solar_flux_w_m2=0.0,
        geothermal_flux_w_m2=0.05,
        cell_count=3,
        thickness_m=0.1,
        initial_temperature_k=[215.0, 210.0, 205.0],
        maximum_spinup_cycles=8,
        spinup_tolerance_k=0.05,
        material_overrides=_constant_material_overrides(
            heat_capacity_c0_j_kg_k=500.0,
            heat_capacity_c1_j_kg_k2=1.5,
            heat_capacity_c2_j_kg_k3=0.002,
            contact_conductivity_w_m_k=0.03,
            density_kg_m3=1200.0,
        ),
    )
    report = expect_success(paths, tmp_path / "report.json")
    ref = build_report(paths.data_dir)
    data = load_solver_data(paths.data_dir)
    material = data.materials["lunar_regolith"]
    # Analytic enthalpy identity used by the energy residual.
    sample_t = 250.0
    analytic = cell_energy(material, 0.1, sample_t)
    linear = material.density_kg_m3 * 0.1 * material.heat_capacity_c0_j_kg_k * sample_t
    assert analytic > linear
    assert heat_capacity(material, sample_t) > material.heat_capacity_c0_j_kg_k

    got = temperature_map(report)
    exp = temperature_map(ref)
    assert_same_keys(got, exp, label="cp temperatures")
    for key, expected in exp.items():
        assert_close(got[key], expected, abs_tol=1.0e-4, label=f"cp T{key}")

    # Constant-c0 control must differ after the same geothermal forcing.
    control = copy_fixture_tree(tmp_path / "control")
    configure_micro_case(
        control,
        case_id="case_cp",
        period_s=600.0,
        time_step_s=100.0,
        solar_flux_w_m2=0.0,
        geothermal_flux_w_m2=0.05,
        cell_count=3,
        thickness_m=0.1,
        initial_temperature_k=[215.0, 210.0, 205.0],
        maximum_spinup_cycles=8,
        spinup_tolerance_k=0.05,
        material_overrides=_constant_material_overrides(
            heat_capacity_c0_j_kg_k=500.0,
            contact_conductivity_w_m_k=0.03,
            density_kg_m3=1200.0,
        ),
    )
    control_ref = temperature_map(build_report(control.data_dir))
    deltas = [abs(got[key] - control_ref[key]) for key in got]
    assert max(deltas) > 1.0e-4


def test_05_nonuniform_grid_stability(tmp_path: Path) -> None:
    """Strongly nonuniform but valid depths remain stable and match the reference."""
    paths = copy_fixture_tree(tmp_path)
    configure_micro_case(
        paths,
        case_id="case_nu",
        period_s=600.0,
        time_step_s=100.0,
        solar_flux_w_m2=0.0,
        geothermal_flux_w_m2=0.02,
        cell_count=5,
        thickness_m=0.05,
        initial_temperature_k=200.0,
        maximum_spinup_cycles=12,
        spinup_tolerance_k=0.5,
        material_overrides=_constant_material_overrides(
            contact_conductivity_w_m_k=0.08,
        ),
    )
    write_depth_grid(
        paths,
        [
            {
                "case_id": "case_nu",
                "cell_index": 0,
                "top_depth_m": 0.0,
                "bottom_depth_m": 0.02,
                "material_id": "lunar_regolith",
                "initial_temperature_k": 205.0,
            },
            {
                "case_id": "case_nu",
                "cell_index": 1,
                "top_depth_m": 0.02,
                "bottom_depth_m": 0.05,
                "material_id": "lunar_regolith",
                "initial_temperature_k": 200.0,
            },
            {
                "case_id": "case_nu",
                "cell_index": 2,
                "top_depth_m": 0.05,
                "bottom_depth_m": 0.12,
                "material_id": "lunar_regolith",
                "initial_temperature_k": 195.0,
            },
            {
                "case_id": "case_nu",
                "cell_index": 3,
                "top_depth_m": 0.12,
                "bottom_depth_m": 0.28,
                "material_id": "lunar_regolith",
                "initial_temperature_k": 190.0,
            },
            {
                "case_id": "case_nu",
                "cell_index": 4,
                "top_depth_m": 0.28,
                "bottom_depth_m": 0.60,
                "material_id": "lunar_regolith",
                "initial_temperature_k": 185.0,
            },
        ],
    )
    report = expect_success(paths, tmp_path / "report.json")
    ref = build_report(paths.data_dir)
    got = temperature_map(report)
    exp = temperature_map(ref)
    assert_same_keys(got, exp, label="nonuniform temperatures")
    for key, expected in exp.items():
        assert_close(got[key], expected, abs_tol=1.0e-4, label=f"nu T{key}")
    assert all(math.isfinite(value) for value in got.values())
    diag = diagnostics_for_case(report, "case_nu")
    assert diag["all_values_finite"] is True


# ---------------------------------------------------------------------------
# Surface forcing tests
# ---------------------------------------------------------------------------


def test_06_albedo_absorption(tmp_path: Path) -> None:
    """Higher albedo alone reduces absorbed solar flux and cools the surface."""
    paths = copy_fixture_tree(tmp_path)
    configure_micro_case(
        paths,
        case_id="case_alb",
        period_s=400.0,
        time_step_s=100.0,
        solar_flux_w_m2=500.0,
        geothermal_flux_w_m2=0.0,
        cos_incidence=0.5,
        cell_count=2,
        thickness_m=0.15,
        initial_temperature_k=230.0,
        maximum_spinup_cycles=12,
        spinup_tolerance_k=1.5,
        observation_times_s=[400.0],
        material_overrides={
            "surface_albedo": 0.1,
            "surface_emissivity": 0.9,
            "heat_capacity_c1_j_kg_k2": 0.0,
            "heat_capacity_c2_j_kg_k3": 0.0,
            "conductivity_depth_gradient_per_m": 0.0,
            "radiative_conductivity_w_m_k4": 0.0,
            "contact_conductivity_w_m_k": 0.1,
            "density_kg_m3": 1000.0,
            "heat_capacity_c0_j_kg_k": 600.0,
        },
    )
    low = expect_success(paths, tmp_path / "low.json")
    low_ref = build_report(paths.data_dir)

    set_material_field(paths, "lunar_regolith", "surface_albedo", 0.55)
    high = expect_success(paths, tmp_path / "high.json")
    high_ref = build_report(paths.data_dir)

    low_flux = max(float(row["absorbed_solar_flux_w_m2"]) for row in flux_rows_for_case(low, "case_alb"))
    high_flux = max(float(row["absorbed_solar_flux_w_m2"]) for row in flux_rows_for_case(high, "case_alb"))
    assert low_flux > high_flux
    assert_close(low_flux, 500.0 * 0.5 * (1.0 - 0.1), abs_tol=1.0e-6, label="low albedo absorb")
    assert_close(high_flux, 500.0 * 0.5 * (1.0 - 0.55), abs_tol=1.0e-6, label="high albedo absorb")

    low_t = max(temperature_map(low).values())
    high_t = max(temperature_map(high).values())
    assert low_t > high_t
    assert_close(
        max(temperature_map(low_ref).values()),
        low_t,
        abs_tol=1.0e-4,
        label="albedo low ref",
    )
    assert_close(
        max(temperature_map(high_ref).values()),
        high_t,
        abs_tol=1.0e-4,
        label="albedo high ref",
    )


def test_07_nonlinear_radiative_cooling(tmp_path: Path) -> None:
    """Hot no-solar surface cools with emitted flux following epsilon sigma T^4."""
    paths = copy_fixture_tree(tmp_path)
    t0 = 350.0
    emissivity = 0.9
    configure_micro_case(
        paths,
        case_id="case_cool",
        period_s=300.0,
        time_step_s=100.0,
        solar_flux_w_m2=0.0,
        geothermal_flux_w_m2=0.0,
        cell_count=2,
        thickness_m=0.05,
        initial_temperature_k=t0,
        maximum_spinup_cycles=1,
        spinup_tolerance_k=1.0e6,
        material_overrides={
            "surface_emissivity": emissivity,
            "surface_albedo": 0.0,
            "heat_capacity_c1_j_kg_k2": 0.0,
            "heat_capacity_c2_j_kg_k3": 0.0,
            "conductivity_depth_gradient_per_m": 0.0,
            "radiative_conductivity_w_m_k4": 0.0,
            "contact_conductivity_w_m_k": 0.01,
            "density_kg_m3": 1100.0,
            "heat_capacity_c0_j_kg_k": 800.0,
        },
    )
    report = expect_success(paths, tmp_path / "report.json")
    ref = build_report(paths.data_dir)
    cfg = load_solver_data(paths.data_dir).config
    first = flux_rows_for_case(report, "case_cool")[0]
    first_ref = flux_rows_for_case(ref, "case_cool")[0]
    emitted = float(first["emitted_thermal_flux_w_m2"])
    assert emitted > 0.0
    assert_close(
        emitted,
        float(first_ref["emitted_thermal_flux_w_m2"]),
        abs_tol=1.0e-4,
        label="emitted flux",
    )
    # Surface must cool below the hot initial state.
    surface_keys = [key for key in temperature_map(report) if key[2] == 0]
    assert temperature_map(report)[surface_keys[0]] < t0
    # Order-of-magnitude check against sigma T^4 near the initial temperature.
    sigma_t4 = emissivity * cfg.stefan_boltzmann_w_m2_k4 * (t0**4)
    assert emitted < sigma_t4
    assert emitted > 0.2 * sigma_t4


def test_08_day_night_clipping(tmp_path: Path) -> None:
    """Negative incidence angles clip to zero absorbed solar flux."""
    paths = copy_fixture_tree(tmp_path)
    configure_micro_case(
        paths,
        case_id="case_clip",
        period_s=400.0,
        time_step_s=100.0,
        solar_flux_w_m2=800.0,
        geothermal_flux_w_m2=0.0,
        cos_incidence=-0.4,
        cell_count=2,
        thickness_m=0.15,
        initial_temperature_k=230.0,
        maximum_spinup_cycles=12,
        spinup_tolerance_k=1.5,
        material_overrides={
            "surface_albedo": 0.15,
            "surface_emissivity": 0.9,
            "heat_capacity_c1_j_kg_k2": 0.0,
            "heat_capacity_c2_j_kg_k3": 0.0,
            "conductivity_depth_gradient_per_m": 0.0,
            "radiative_conductivity_w_m_k4": 0.0,
            "contact_conductivity_w_m_k": 0.1,
            "density_kg_m3": 1000.0,
            "heat_capacity_c0_j_kg_k": 600.0,
        },
    )
    # Also include a night-to-day interval that starts negative and ends positive.
    write_forcing_intervals(
        paths,
        [
            {
                "case_id": "case_clip",
                "interval_seq": 1,
                "start_time_s": 0.0,
                "end_time_s": 200.0,
                "cos_incidence_start": -0.5,
                "cos_incidence_end": -0.1,
                "eclipse_profile_id": "none",
            },
            {
                "case_id": "case_clip",
                "interval_seq": 2,
                "start_time_s": 200.0,
                "end_time_s": 400.0,
                "cos_incidence_start": -0.1,
                "cos_incidence_end": 0.8,
                "eclipse_profile_id": "none",
            },
        ],
    )
    report = expect_success(paths, tmp_path / "report.json")
    data = load_solver_data(paths.data_dir)
    case = data.illumination_cases["case_clip"]
    material = data.materials["lunar_regolith"]
    night = absorbed_solar_flux(
        case,
        material,
        data.forcing_intervals["case_clip"],
        data.eclipse_profiles,
        100.0,
        case.albedo_offset,
    )
    assert_close(night, 0.0, abs_tol=1.0e-12, label="analytic night absorb")
    for row in flux_rows_for_case(report, "case_clip"):
        absorbed = float(row["absorbed_solar_flux_w_m2"])
        assert absorbed >= -1.0e-12
        if float(row["end_time_s"]) <= 200.0:
            assert_close(absorbed, 0.0, abs_tol=1.0e-9, label="clipped step")


def test_09_partial_eclipse_interpolation(tmp_path: Path) -> None:
    """Interior eclipse-profile times use linear transmission interpolation."""
    paths = copy_fixture_tree(tmp_path)
    write_eclipse_profiles(
        paths,
        [
            {
                "eclipse_profile_id": "none",
                "profile_time_s": 0.0,
                "transmission_fraction": 1.0,
            },
            {
                "eclipse_profile_id": "none",
                "profile_time_s": 600.0,
                "transmission_fraction": 1.0,
            },
            {
                "eclipse_profile_id": "partial_eclipse",
                "profile_time_s": 0.0,
                "transmission_fraction": 1.0,
            },
            {
                "eclipse_profile_id": "partial_eclipse",
                "profile_time_s": 200.0,
                "transmission_fraction": 0.2,
            },
            {
                "eclipse_profile_id": "partial_eclipse",
                "profile_time_s": 400.0,
                "transmission_fraction": 0.2,
            },
            {
                "eclipse_profile_id": "partial_eclipse",
                "profile_time_s": 600.0,
                "transmission_fraction": 1.0,
            },
        ],
    )
    configure_micro_case(
        paths,
        case_id="case_eclip",
        period_s=600.0,
        time_step_s=100.0,
        solar_flux_w_m2=500.0,
        geothermal_flux_w_m2=0.0,
        cos_incidence=0.5,
        eclipse_profile_id="partial_eclipse",
        cell_count=2,
        thickness_m=0.15,
        initial_temperature_k=230.0,
        maximum_spinup_cycles=12,
        spinup_tolerance_k=1.5,
        material_overrides={
            "surface_albedo": 0.0,
            "surface_emissivity": 0.9,
            "heat_capacity_c1_j_kg_k2": 0.0,
            "heat_capacity_c2_j_kg_k3": 0.0,
            "conductivity_depth_gradient_per_m": 0.0,
            "radiative_conductivity_w_m_k4": 0.0,
            "contact_conductivity_w_m_k": 0.1,
            "density_kg_m3": 1000.0,
            "heat_capacity_c0_j_kg_k": 600.0,
        },
    )
    report = expect_success(paths, tmp_path / "report.json")
    data = load_solver_data(paths.data_dir)
    mid = eclipse_transmission_at_time(data.eclipse_profiles, "partial_eclipse", 100.0)
    assert_close(mid, 0.6, abs_tol=1.0e-12, label="interp transmission")
    expected_absorb = 500.0 * 0.5 * mid
    # Candidate report step ending at 100 s must match the interpolated absorption.
    step = next(
        row
        for row in flux_rows_for_case(report, "case_eclip")
        if abs(float(row["end_time_s"]) - 100.0) < 1.0e-9
    )
    assert_close(
        float(step["absorbed_solar_flux_w_m2"]),
        expected_absorb,
        abs_tol=1.0e-6,
        label="interp absorb",
    )


def test_10_eclipse_reheating(tmp_path: Path) -> None:
    """Surface cools while transmission is low and reheats when it recovers."""
    paths = copy_fixture_tree(tmp_path)
    write_eclipse_profiles(
        paths,
        [
            {"eclipse_profile_id": "none", "profile_time_s": 0.0, "transmission_fraction": 1.0},
            {"eclipse_profile_id": "none", "profile_time_s": 600.0, "transmission_fraction": 1.0},
            {
                "eclipse_profile_id": "partial_eclipse",
                "profile_time_s": 0.0,
                "transmission_fraction": 1.0,
            },
            {
                "eclipse_profile_id": "partial_eclipse",
                "profile_time_s": 200.0,
                "transmission_fraction": 0.1,
            },
            {
                "eclipse_profile_id": "partial_eclipse",
                "profile_time_s": 400.0,
                "transmission_fraction": 0.1,
            },
            {
                "eclipse_profile_id": "partial_eclipse",
                "profile_time_s": 600.0,
                "transmission_fraction": 1.0,
            },
        ],
    )
    configure_micro_case(
        paths,
        case_id="case_reheat",
        period_s=600.0,
        time_step_s=100.0,
        solar_flux_w_m2=500.0,
        geothermal_flux_w_m2=0.0,
        cos_incidence=0.5,
        eclipse_profile_id="partial_eclipse",
        cell_count=2,
        thickness_m=0.15,
        initial_temperature_k=230.0,
        maximum_spinup_cycles=15,
        spinup_tolerance_k=1.5,
        observation_times_s=[200.0, 400.0, 600.0],
        material_overrides={
            "surface_albedo": 0.15,
            "surface_emissivity": 0.9,
            "heat_capacity_c1_j_kg_k2": 0.0,
            "heat_capacity_c2_j_kg_k3": 0.0,
            "conductivity_depth_gradient_per_m": 0.0,
            "radiative_conductivity_w_m_k4": 0.0,
            "contact_conductivity_w_m_k": 0.1,
            "density_kg_m3": 1000.0,
            "heat_capacity_c0_j_kg_k": 600.0,
        },
    )
    report = expect_success(paths, tmp_path / "report.json")
    ref = build_report(paths.data_dir)
    rad = radiometer_map(report)
    rad_ref = radiometer_map(ref)
    assert_same_keys(rad, rad_ref, label="reheat radiometer")
    t_mid = float(rad["obs_case_reheat_0"]["surface_temperature_k"])
    t_dark = float(rad["obs_case_reheat_1"]["surface_temperature_k"])
    t_end = float(rad["obs_case_reheat_2"]["surface_temperature_k"])
    assert t_dark < t_mid
    assert t_end > t_dark
    for obs_id, row in rad.items():
        assert_close(
            float(row["surface_temperature_k"]),
            float(rad_ref[obs_id]["surface_temperature_k"]),
            abs_tol=1.0e-3,
            label=f"reheat {obs_id}",
        )


# ---------------------------------------------------------------------------
# Spin-up and conductivity tests
# ---------------------------------------------------------------------------


def test_11_periodic_spinup(tmp_path: Path) -> None:
    """Spin-up cycle count and converged profile match the independent reference."""
    paths = copy_fixture_tree(tmp_path)
    configure_micro_case(
        paths,
        case_id="case_spin",
        period_s=300.0,
        time_step_s=100.0,
        solar_flux_w_m2=800.0,
        geothermal_flux_w_m2=0.0,
        cos_incidence=1.0,
        cell_count=2,
        thickness_m=0.05,
        initial_temperature_k=50.0,
        maximum_spinup_cycles=40,
        spinup_tolerance_k=13.2,
        material_overrides={
            "surface_albedo": 0.1,
            "surface_emissivity": 0.95,
            "heat_capacity_c1_j_kg_k2": 0.0,
            "heat_capacity_c2_j_kg_k3": 0.0,
            "conductivity_depth_gradient_per_m": 0.0,
            "radiative_conductivity_w_m_k4": 0.0,
            "contact_conductivity_w_m_k": 0.05,
            "density_kg_m3": 800.0,
            "heat_capacity_c0_j_kg_k": 400.0,
        },
    )
    report = expect_success(paths, tmp_path / "report.json")
    ref = build_report(paths.data_dir)
    got_diag = diagnostics_for_case(report, "case_spin")
    exp_diag = diagnostics_for_case(ref, "case_spin")
    assert int(got_diag["spinup_cycles"]) == int(exp_diag["spinup_cycles"])
    assert int(got_diag["spinup_cycles"]) >= 2
    assert_close(
        float(got_diag["final_spinup_difference_k"]),
        float(exp_diag["final_spinup_difference_k"]),
        abs_tol=1.0e-4,
        label="spinup delta",
    )
    got = temperature_map(report)
    exp = temperature_map(ref)
    assert_same_keys(got, exp, label="spinup temperatures")
    for key, expected in exp.items():
        assert_close(got[key], expected, abs_tol=1.0e-3, label=f"spin T{key}")


def test_12_insufficient_spinup_fatal(tmp_path: Path) -> None:
    """Too-small maximum_spinup_cycles must fail fatally without leaving artifacts."""
    paths = copy_fixture_tree(tmp_path)
    configure_micro_case(
        paths,
        case_id="case_fatal",
        period_s=800.0,
        time_step_s=100.0,
        solar_flux_w_m2=1300.0,
        geothermal_flux_w_m2=0.0,
        cos_incidence=1.0,
        cell_count=4,
        initial_temperature_k=[120.0, 140.0, 160.0, 180.0],
        maximum_spinup_cycles=1,
        spinup_tolerance_k=1.0e-4,
        material_overrides={
            "surface_albedo": 0.1,
            "surface_emissivity": 0.95,
            "heat_capacity_c1_j_kg_k2": 0.0,
            "heat_capacity_c2_j_kg_k3": 0.0,
            "conductivity_depth_gradient_per_m": 0.0,
            "radiative_conductivity_w_m_k4": 0.0,
            "contact_conductivity_w_m_k": 0.01,
        },
    )
    expect_failure(paths, tmp_path / "report.json")


def test_13_conductivity_gradient(tmp_path: Path) -> None:
    """Per-cell contact conductivity must use depth centers; gamma must change T."""
    paths = copy_fixture_tree(tmp_path)
    # Insulated relaxation from a strong depth gradient: gamma changes face
    # resistances without relying on a hidden geothermal warm-start.
    configure_micro_case(
        paths,
        case_id="case_grad",
        period_s=600.0,
        time_step_s=100.0,
        solar_flux_w_m2=0.0,
        geothermal_flux_w_m2=0.0,
        cell_count=5,
        thickness_m=0.1,
        initial_temperature_k=[280.0, 250.0, 220.0, 190.0, 160.0],
        maximum_spinup_cycles=1,
        spinup_tolerance_k=1.0e6,
        material_overrides=_constant_material_overrides(
            contact_conductivity_w_m_k=0.01,
            conductivity_depth_gradient_per_m=0.0,
            density_kg_m3=1200.0,
            heat_capacity_c0_j_kg_k=600.0,
        ),
    )
    baseline = expect_success(paths, tmp_path / "base.json")
    baseline_ref = build_report(paths.data_dir)

    gamma = 8.0
    set_material_field(
        paths, "lunar_regolith", "conductivity_depth_gradient_per_m", gamma
    )
    mutated = expect_success(paths, tmp_path / "grad.json")
    mutated_ref = build_report(paths.data_dir)

    base_map = temperature_map(baseline)
    mut_map = temperature_map(mutated)
    assert_same_keys(base_map, mut_map, label="gradient keys")
    deltas = [abs(mut_map[key] - base_map[key]) for key in base_map]
    assert max(deltas) > 1.0e-3

    # Public identity: deeper centers must see a larger contact factor.
    data = load_solver_data(paths.data_dir)
    material = data.materials["lunar_regolith"]
    shallow_z = 0.05  # center of first 0.1 m cell
    deep_z = 0.45  # center of fifth cell
    k_shallow = cell_conductivity(material, 200.0, shallow_z, 1.0)
    k_deep = cell_conductivity(material, 200.0, deep_z, 1.0)
    assert k_deep > k_shallow * 1.5
    assert_close(
        k_shallow,
        material.contact_conductivity_w_m_k * (1.0 + gamma * shallow_z),
        abs_tol=1.0e-12,
        label="shallow k identity",
    )
    assert_close(
        k_deep,
        material.contact_conductivity_w_m_k * (1.0 + gamma * deep_z),
        abs_tol=1.0e-12,
        label="deep k identity",
    )

    for key, expected in temperature_map(mutated_ref).items():
        assert_close(mut_map[key], expected, abs_tol=0.05, rel_tol=2.0e-5, label=f"grad T{key}")
    for key, expected in temperature_map(baseline_ref).items():
        assert_close(base_map[key], expected, abs_tol=0.05, rel_tol=2.0e-5, label=f"base T{key}")


def test_14_radiative_conductivity(tmp_path: Path) -> None:
    """T^3 radiative conductivity affects hot columns more than cold ones."""
    def build_case(root: Path, temperature: float, rad_k: float) -> Dict[str, Any]:
        paths = copy_fixture_tree(root)
        configure_micro_case(
            paths,
            case_id="case_radk",
            period_s=500.0,
            time_step_s=100.0,
            solar_flux_w_m2=0.0,
            geothermal_flux_w_m2=0.0,
            cell_count=3,
            thickness_m=0.1,
            initial_temperature_k=[temperature, temperature - 30.0, temperature - 50.0],
            maximum_spinup_cycles=1,
            spinup_tolerance_k=1.0e6,
            material_overrides=_constant_material_overrides(
                contact_conductivity_w_m_k=0.005,
                radiative_conductivity_w_m_k4=rad_k,
                density_kg_m3=1300.0,
                heat_capacity_c0_j_kg_k=700.0,
            ),
        )
        report = expect_success(paths, root / "report.json")
        ref = build_report(paths.data_dir)
        return {"report": report, "ref": ref, "paths": paths}

    cold_off = build_case(tmp_path / "cold_off", 180.0, 0.0)
    cold_on = build_case(tmp_path / "cold_on", 180.0, 2.0e-8)
    hot_off = build_case(tmp_path / "hot_off", 320.0, 0.0)
    hot_on = build_case(tmp_path / "hot_on", 320.0, 2.0e-8)

    def spread(report: Mapping[str, Any]) -> float:
        values = list(temperature_map(report).values())
        return max(values) - min(values)

    cold_delta = abs(spread(cold_on["report"]) - spread(cold_off["report"]))
    hot_delta = abs(spread(hot_on["report"]) - spread(hot_off["report"]))
    assert hot_delta > cold_delta
    data = load_solver_data(hot_on["paths"].data_dir)
    material = data.materials["lunar_regolith"]
    k_hot = cell_conductivity(material, 320.0, 0.05, 1.0)
    k_cold = cell_conductivity(material, 180.0, 0.05, 1.0)
    assert k_hot > k_cold
    for bundle in (cold_on, hot_on):
        got = temperature_map(bundle["report"])
        exp = temperature_map(bundle["ref"])
        for key, expected in exp.items():
            assert_close(got[key], expected, abs_tol=1.0e-3, label=f"radk {key}")


def test_15_energy_balance(tmp_path: Path) -> None:
    """Every report-step energy residual reconstructs within configured tolerance."""
    paths = copy_fixture_tree(tmp_path)
    configure_micro_case(
        paths,
        case_id="case_energy",
        period_s=400.0,
        time_step_s=100.0,
        solar_flux_w_m2=400.0,
        geothermal_flux_w_m2=0.03,
        cos_incidence=0.4,
        cell_count=2,
        thickness_m=0.15,
        initial_temperature_k=230.0,
        maximum_spinup_cycles=12,
        spinup_tolerance_k=1.5,
        material_overrides={
            "surface_albedo": 0.15,
            "surface_emissivity": 0.9,
            "heat_capacity_c1_j_kg_k2": 0.0,
            "heat_capacity_c2_j_kg_k3": 0.0,
            "conductivity_depth_gradient_per_m": 0.0,
            "radiative_conductivity_w_m_k4": 0.0,
            "contact_conductivity_w_m_k": 0.1,
            "density_kg_m3": 1000.0,
            "heat_capacity_c0_j_kg_k": 600.0,
        },
    )
    report = expect_success(paths, tmp_path / "report.json")
    ref = build_report(paths.data_dir)
    cfg = load_solver_data(paths.data_dir).config
    tol = cfg.energy_balance_tolerance_j_m2
    got_rows = index_unique(
        flux_rows_for_case(report, "case_energy"),
        lambda row: int(row["step_index"]),
    )
    exp_rows = index_unique(
        flux_rows_for_case(ref, "case_energy"),
        lambda row: int(row["step_index"]),
    )
    assert_same_keys(got_rows, exp_rows, label="energy steps")
    for step_index, row in got_rows.items():
        stored = assert_finite_number(row["stored_energy_change_j_m2"], "stored")
        net = assert_finite_number(row["net_boundary_energy_j_m2"], "net")
        residual = assert_finite_number(row["energy_residual_j_m2"], "residual")
        assert_close(residual, stored - net, abs_tol=1.0e-6, label="identity")
        assert abs(residual) <= tol
        assert_close(
            residual,
            float(exp_rows[step_index]["energy_residual_j_m2"]),
            abs_tol=1.0e-4,
            label=f"energy step {step_index}",
        )
    assert float(report["summary"]["maximum_absolute_energy_residual_j_m2"]) <= tol


# ---------------------------------------------------------------------------
# Radiometry tests
# ---------------------------------------------------------------------------


def test_16_planck_monotonicity(tmp_path: Path) -> None:
    """Hotter surfaces produce larger band radiance matching the reference Planck model."""
    paths = copy_fixture_tree(tmp_path)
    configure_micro_case(
        paths,
        case_id="case_planck",
        period_s=400.0,
        time_step_s=100.0,
        solar_flux_w_m2=0.0,
        geothermal_flux_w_m2=0.0,
        cell_count=2,
        initial_temperature_k=280.0,
        maximum_spinup_cycles=2,
        spinup_tolerance_k=1000.0,
        material_overrides=_constant_material_overrides(surface_emissivity=0.95),
        observation_times_s=[400.0],
        band_id="band_8um",
    )
    cold = expect_success(paths, tmp_path / "cold.json")
    cold_ref = build_report(paths.data_dir)

    write_uniform_depth_grid(
        paths,
        case_id="case_planck",
        cell_count=2,
        thickness_m=0.1,
        material_id="lunar_regolith",
        initial_temperature_k=320.0,
    )
    hot = expect_success(paths, tmp_path / "hot.json")
    hot_ref = build_report(paths.data_dir)

    cold_row = radiometer_map(cold)["obs_case_planck_0"]
    hot_row = radiometer_map(hot)["obs_case_planck_0"]
    assert float(hot_row["band_radiance_w_m2_sr"]) > float(cold_row["band_radiance_w_m2_sr"])
    assert float(hot_row["brightness_temperature_k"]) > float(
        cold_row["brightness_temperature_k"]
    )
    data = load_solver_data(paths.data_dir)
    samples = data.radiometer_bands["band_8um"]
    hot_t = float(hot_row["surface_temperature_k"])
    analytic = band_radiance(samples, hot_t, 0.95, data.config)
    assert_close(
        float(hot_row["band_radiance_w_m2_sr"]),
        analytic,
        abs_tol=1.0e-8,
        rel_tol=1.0e-6,
        label="planck analytic",
    )
    assert_close(
        float(hot_row["band_radiance_w_m2_sr"]),
        float(radiometer_map(hot_ref)["obs_case_planck_0"]["band_radiance_w_m2_sr"]),
        abs_tol=1.0e-6,
        label="planck ref",
    )
    assert_close(
        float(cold_row["band_radiance_w_m2_sr"]),
        float(radiometer_map(cold_ref)["obs_case_planck_0"]["band_radiance_w_m2_sr"]),
        abs_tol=1.0e-6,
        label="planck cold ref",
    )


def test_17_band_normalization(tmp_path: Path) -> None:
    """Scaling an entire response curve leaves normalized radiance unchanged."""
    paths = copy_fixture_tree(tmp_path)
    configure_micro_case(
        paths,
        case_id="case_norm",
        period_s=300.0,
        time_step_s=100.0,
        solar_flux_w_m2=0.0,
        geothermal_flux_w_m2=0.0,
        cell_count=2,
        initial_temperature_k=260.0,
        maximum_spinup_cycles=2,
        spinup_tolerance_k=1000.0,
        material_overrides=_constant_material_overrides(surface_emissivity=0.97),
        band_id="band_8um",
    )
    base = expect_success(paths, tmp_path / "base.json")
    scale_band_responses(paths, "band_8um", 3.5)
    scaled = expect_success(paths, tmp_path / "scaled.json")
    cfg = load_solver_data(paths.data_dir).config
    base_row = radiometer_map(base)["obs_case_norm_0"]
    scaled_row = radiometer_map(scaled)["obs_case_norm_0"]
    assert_close(
        float(scaled_row["band_radiance_w_m2_sr"]),
        float(base_row["band_radiance_w_m2_sr"]),
        abs_tol=1.0e-8,
        rel_tol=1.0e-12,
        label="normalized radiance",
    )
    assert_close(
        float(scaled_row["brightness_temperature_k"]),
        float(base_row["brightness_temperature_k"]),
        abs_tol=cfg.brightness_temperature_tolerance_k * 10.0,
        label="normalized Tb",
    )


def test_18_band_integration(tmp_path: Path) -> None:
    """Trapezoidal integration over a nonuniform wavelength grid matches reference."""
    paths = copy_fixture_tree(tmp_path)
    write_radiometer_bands(
        paths,
        [
            {"band_id": "band_nu", "sample_index": 0, "wavelength_um": 6.0, "response": 0.1},
            {"band_id": "band_nu", "sample_index": 1, "wavelength_um": 7.5, "response": 0.8},
            {"band_id": "band_nu", "sample_index": 2, "wavelength_um": 8.0, "response": 1.0},
            {"band_id": "band_nu", "sample_index": 3, "wavelength_um": 10.5, "response": 0.4},
            {"band_id": "band_nu", "sample_index": 4, "wavelength_um": 12.0, "response": 0.05},
            # Keep an unused second band so schema remains valid if referenced elsewhere.
            {"band_id": "band_25um", "sample_index": 0, "wavelength_um": 20.0, "response": 0.3},
            {"band_id": "band_25um", "sample_index": 1, "wavelength_um": 25.0, "response": 1.0},
            {"band_id": "band_25um", "sample_index": 2, "wavelength_um": 30.0, "response": 0.2},
        ],
    )
    configure_micro_case(
        paths,
        case_id="case_trap",
        period_s=300.0,
        time_step_s=100.0,
        solar_flux_w_m2=0.0,
        geothermal_flux_w_m2=0.0,
        cell_count=2,
        initial_temperature_k=275.0,
        maximum_spinup_cycles=2,
        spinup_tolerance_k=1000.0,
        material_overrides=_constant_material_overrides(surface_emissivity=1.0),
        band_id="band_nu",
    )
    report = expect_success(paths, tmp_path / "report.json")
    ref = build_report(paths.data_dir)
    row = radiometer_map(report)["obs_case_trap_0"]
    row_ref = radiometer_map(ref)["obs_case_trap_0"]
    data = load_solver_data(paths.data_dir)
    samples = data.radiometer_bands["band_nu"]
    analytic = band_radiance(
        samples, float(row["surface_temperature_k"]), 1.0, data.config
    )
    assert_close(
        float(row["band_radiance_w_m2_sr"]),
        analytic,
        abs_tol=1.0e-10,
        rel_tol=1.0e-6,
        label="trap",
    )
    assert_close(
        float(row["band_radiance_w_m2_sr"]),
        float(row_ref["band_radiance_w_m2_sr"]),
        abs_tol=1.0e-6,
        label="trap ref",
    )
    # Explicit nonuniform spacing check: adjacent deltas are not equal.
    wavelengths = [sample.wavelength_um for sample in samples]
    deltas = [wavelengths[i + 1] - wavelengths[i] for i in range(len(wavelengths) - 1)]
    assert len(set(round(delta, 12) for delta in deltas)) > 1


def test_19_brightness_inversion(tmp_path: Path) -> None:
    """Forward band radiance inverts back to the known blackbody brightness temperature."""
    paths = copy_fixture_tree(tmp_path)
    target_t = 295.0
    configure_micro_case(
        paths,
        case_id="case_tb",
        period_s=300.0,
        time_step_s=100.0,
        solar_flux_w_m2=0.0,
        geothermal_flux_w_m2=0.0,
        cell_count=2,
        initial_temperature_k=target_t,
        maximum_spinup_cycles=2,
        spinup_tolerance_k=1000.0,
        material_overrides=_constant_material_overrides(surface_emissivity=1.0),
        band_id="band_8um",
    )
    report = expect_success(paths, tmp_path / "report.json")
    data = load_solver_data(paths.data_dir)
    cfg = data.config
    row = radiometer_map(report)["obs_case_tb_0"]
    samples = data.radiometer_bands["band_8um"]
    radiance = float(row["band_radiance_w_m2_sr"])
    recovered = brightness_temperature(samples, radiance, cfg)
    surface_t = float(row["surface_temperature_k"])
    assert_close(
        float(row["brightness_temperature_k"]),
        recovered,
        abs_tol=cfg.brightness_temperature_tolerance_k * 20.0,
        label="Tb row",
    )
    assert_close(
        float(row["brightness_temperature_k"]),
        surface_t,
        abs_tol=cfg.brightness_temperature_tolerance_k,
        label="Tb vs surface",
    )


def test_20_distinct_bands(tmp_path: Path) -> None:
    """Two different response curves at one temperature yield distinct radiometry."""
    paths = copy_fixture_tree(tmp_path)
    configure_micro_case(
        paths,
        case_id="case_bands",
        period_s=300.0,
        time_step_s=100.0,
        solar_flux_w_m2=0.0,
        geothermal_flux_w_m2=0.0,
        cell_count=2,
        initial_temperature_k=270.0,
        maximum_spinup_cycles=2,
        spinup_tolerance_k=1000.0,
        material_overrides=_constant_material_overrides(surface_emissivity=0.96),
    )
    write_observation_queries(
        paths,
        [
            {
                "observation_id": "obs_short",
                "case_id": "case_bands",
                "time_s": 300.0,
                "band_id": "band_8um",
            },
            {
                "observation_id": "obs_long",
                "case_id": "case_bands",
                "time_s": 300.0,
                "band_id": "band_25um",
            },
        ],
    )
    report = expect_success(paths, tmp_path / "report.json")
    ref = build_report(paths.data_dir)
    got = radiometer_map(report)
    exp = radiometer_map(ref)
    assert_same_keys(got, exp, label="band keys")
    assert float(got["obs_short"]["band_radiance_w_m2_sr"]) != float(
        got["obs_long"]["band_radiance_w_m2_sr"]
    )
    for obs_id in ("obs_short", "obs_long"):
        assert_close(
            float(got[obs_id]["band_radiance_w_m2_sr"]),
            float(exp[obs_id]["band_radiance_w_m2_sr"]),
            abs_tol=1.0e-6,
            label=f"{obs_id} radiance",
        )
        assert_close(
            float(got[obs_id]["brightness_temperature_k"]),
            float(exp[obs_id]["brightness_temperature_k"]),
            abs_tol=1.0e-4,
            label=f"{obs_id} Tb",
        )


# ---------------------------------------------------------------------------
# Inversion tests
# ---------------------------------------------------------------------------


def test_21_one_parameter_recovery(tmp_path: Path) -> None:
    """Recover an interior conductivity_scale from synthetic brightness targets."""
    paths = copy_fixture_tree(tmp_path)
    true_scale = 1.12
    configure_micro_case(
        paths,
        case_id="case_fit1",
        period_s=400.0,
        time_step_s=100.0,
        solar_flux_w_m2=600.0,
        geothermal_flux_w_m2=0.0,
        conductivity_scale=1.0,
        cos_incidence=0.6,
        cell_count=2,
        thickness_m=0.15,
        initial_temperature_k=240.0,
        maximum_spinup_cycles=10,
        spinup_tolerance_k=1.0,
        observation_times_s=[200.0, 400.0],
        material_overrides={
            "surface_albedo": 0.2,
            "surface_emissivity": 0.9,
            "heat_capacity_c1_j_kg_k2": 0.0,
            "heat_capacity_c2_j_kg_k3": 0.0,
            "conductivity_depth_gradient_per_m": 0.0,
            "radiative_conductivity_w_m_k4": 0.0,
            "contact_conductivity_w_m_k": 0.08,
            "density_kg_m3": 1000.0,
            "heat_capacity_c0_j_kg_k": 600.0,
        },
        clear_fits=True,
    )
    obs_ids = ["obs_case_fit1_0", "obs_case_fit1_1"]
    targets = compute_brightness_targets(
        paths.data_dir, "case_fit1", true_scale, 0.0, obs_ids
    )
    write_inversion_queries(
        paths,
        [
            {
                "fit_id": "fit_one",
                "case_id": "case_fit1",
                "parameter_names": ["conductivity_scale"],
                "lower_bounds": [0.9],
                "upper_bounds": [1.3],
                "initial_values": [1.0],
                "observation_ids": obs_ids,
                "target_brightness_temperatures_k": targets,
                "observation_weights": [1.0, 1.0],
            }
        ],
    )
    report = expect_success(paths, tmp_path / "report.json")
    cfg = load_solver_data(paths.data_dir).config
    got = index_unique(report["inverse_fit_rows"], lambda row: row["fit_id"])["fit_one"]
    recovered = float(got["parameter_values"][0])
    assert_close(
        recovered,
        true_scale,
        abs_tol=cfg.inversion_parameter_tolerance * 12.0,
        label="one-param truth",
    )
    assert float(got["objective"]) <= cfg.inversion_objective_tolerance
    assert got["converged"] is True
    assert got["at_parameter_bound"] is False
    assert list(got["parameter_names"]) == ["conductivity_scale"]
    assert len(got["parameter_values"]) == 1


def test_22_two_parameter_recovery(tmp_path: Path) -> None:
    """Recover conductivity_scale and albedo_offset from multi-band observations."""
    paths = copy_fixture_tree(tmp_path)
    true_scale = 1.08
    true_albedo = 0.02
    configure_micro_case(
        paths,
        case_id="case_fit2",
        period_s=400.0,
        time_step_s=100.0,
        solar_flux_w_m2=500.0,
        geothermal_flux_w_m2=0.0,
        conductivity_scale=1.0,
        albedo_offset=0.0,
        cos_incidence=0.5,
        cell_count=2,
        thickness_m=0.2,
        initial_temperature_k=230.0,
        maximum_spinup_cycles=15,
        spinup_tolerance_k=1.5,
        material_overrides={
            "surface_albedo": 0.2,
            "surface_emissivity": 0.9,
            "heat_capacity_c1_j_kg_k2": 0.0,
            "heat_capacity_c2_j_kg_k3": 0.0,
            "conductivity_depth_gradient_per_m": 0.0,
            "radiative_conductivity_w_m_k4": 0.0,
            "contact_conductivity_w_m_k": 0.1,
            "density_kg_m3": 1000.0,
            "heat_capacity_c0_j_kg_k": 600.0,
        },
        clear_fits=True,
    )
    write_observation_queries(
        paths,
        [
            {
                "observation_id": "obs_a",
                "case_id": "case_fit2",
                "time_s": 200.0,
                "band_id": "band_8um",
            },
            {
                "observation_id": "obs_b",
                "case_id": "case_fit2",
                "time_s": 400.0,
                "band_id": "band_25um",
            },
        ],
    )
    obs_ids = ["obs_a", "obs_b"]
    targets = compute_brightness_targets(
        paths.data_dir, "case_fit2", true_scale, true_albedo, obs_ids
    )
    write_inversion_queries(
        paths,
        [
            {
                "fit_id": "fit_two",
                "case_id": "case_fit2",
                "parameter_names": ["conductivity_scale", "albedo_offset"],
                "lower_bounds": [0.9, 0.0],
                "upper_bounds": [1.25, 0.04],
                "initial_values": [1.0, 0.0],
                "observation_ids": obs_ids,
                "target_brightness_temperatures_k": targets,
                "observation_weights": [1.0, 1.0],
            }
        ],
    )
    report = expect_success(paths, tmp_path / "report.json")
    cfg = load_solver_data(paths.data_dir).config
    got = index_unique(report["inverse_fit_rows"], lambda row: row["fit_id"])["fit_two"]
    for index, truth in enumerate((true_scale, true_albedo)):
        assert_close(
            float(got["parameter_values"][index]),
            truth,
            abs_tol=cfg.inversion_parameter_tolerance * 16.0,
            label=f"two-param truth {index}",
        )
    assert float(got["objective"]) <= cfg.inversion_objective_tolerance
    assert got["converged"] is True
    assert list(got["parameter_names"]) == ["conductivity_scale", "albedo_offset"]
    assert len(got["parameter_values"]) == 2


def test_23_parameter_bounds(tmp_path: Path) -> None:
    """An unreachable target pins the recovered parameter to a bound."""
    paths = copy_fixture_tree(tmp_path)
    configure_micro_case(
        paths,
        case_id="case_bound",
        period_s=400.0,
        time_step_s=100.0,
        solar_flux_w_m2=500.0,
        geothermal_flux_w_m2=0.0,
        conductivity_scale=1.0,
        cos_incidence=0.5,
        cell_count=2,
        thickness_m=0.2,
        initial_temperature_k=230.0,
        maximum_spinup_cycles=10,
        spinup_tolerance_k=1.5,
        observation_times_s=[400.0],
        material_overrides={
            "surface_albedo": 0.2,
            "surface_emissivity": 0.9,
            "heat_capacity_c1_j_kg_k2": 0.0,
            "heat_capacity_c2_j_kg_k3": 0.0,
            "conductivity_depth_gradient_per_m": 0.0,
            "radiative_conductivity_w_m_k4": 0.0,
            "contact_conductivity_w_m_k": 0.1,
            "density_kg_m3": 1000.0,
            "heat_capacity_c0_j_kg_k": 600.0,
        },
        clear_fits=True,
    )
    write_inversion_queries(
        paths,
        [
            {
                "fit_id": "fit_bound",
                "case_id": "case_bound",
                "parameter_names": ["conductivity_scale"],
                "lower_bounds": [0.9],
                "upper_bounds": [1.2],
                "initial_values": [1.0],
                "observation_ids": ["obs_case_bound_0"],
                "target_brightness_temperatures_k": [400.0],
                "observation_weights": [1.0],
            }
        ],
    )
    report = expect_success(paths, tmp_path / "report.json")
    cfg = load_solver_data(paths.data_dir).config
    got = index_unique(report["inverse_fit_rows"], lambda row: row["fit_id"])["fit_bound"]
    assert got["at_parameter_bound"] is True
    recovered = float(got["parameter_values"][0])
    assert abs(recovered - 0.9) <= cfg.inversion_parameter_tolerance
    assert list(got["parameter_names"]) == ["conductivity_scale"]
    assert len(got["parameter_values"]) == 1



# ---------------------------------------------------------------------------
# Integration and determinism
# ---------------------------------------------------------------------------


def test_24_eclipse_mutation_locality(tmp_path: Path) -> None:
    """Mutating one eclipse profile changes only the case that references it."""
    paths = copy_fixture_tree(tmp_path)
    update_solver_config(paths, time_step_s=100.0)
    write_illumination_cases(
        paths,
        [
            {
                "case_id": "case_diurnal",
                "period_s": 600.0,
                "solar_flux_w_m2": 500.0,
                "geothermal_flux_w_m2": 0.0,
                "conductivity_scale": 1.0,
                "albedo_offset": 0.0,
                "spinup_tolerance_k": 1.5,
                "maximum_spinup_cycles": 10,
            },
            {
                "case_id": "case_eclipse",
                "period_s": 600.0,
                "solar_flux_w_m2": 500.0,
                "geothermal_flux_w_m2": 0.0,
                "conductivity_scale": 1.0,
                "albedo_offset": 0.0,
                "spinup_tolerance_k": 1.5,
                "maximum_spinup_cycles": 10,
            },
        ],
    )
    write_depth_grid(
        paths,
        [
            {
                "case_id": "case_diurnal",
                "cell_index": 0,
                "top_depth_m": 0.0,
                "bottom_depth_m": 0.15,
                "material_id": "lunar_regolith",
                "initial_temperature_k": 230.0,
            },
            {
                "case_id": "case_diurnal",
                "cell_index": 1,
                "top_depth_m": 0.15,
                "bottom_depth_m": 0.3,
                "material_id": "lunar_regolith",
                "initial_temperature_k": 230.0,
            },
            {
                "case_id": "case_eclipse",
                "cell_index": 0,
                "top_depth_m": 0.0,
                "bottom_depth_m": 0.15,
                "material_id": "lunar_regolith",
                "initial_temperature_k": 230.0,
            },
            {
                "case_id": "case_eclipse",
                "cell_index": 1,
                "top_depth_m": 0.15,
                "bottom_depth_m": 0.3,
                "material_id": "lunar_regolith",
                "initial_temperature_k": 230.0,
            },
        ],
    )
    write_forcing_intervals(
        paths,
        [
            {
                "case_id": "case_diurnal",
                "interval_seq": 1,
                "start_time_s": 0.0,
                "end_time_s": 600.0,
                "cos_incidence_start": 0.5,
                "cos_incidence_end": 0.5,
                "eclipse_profile_id": "none",
            },
            {
                "case_id": "case_eclipse",
                "interval_seq": 1,
                "start_time_s": 0.0,
                "end_time_s": 600.0,
                "cos_incidence_start": 0.5,
                "cos_incidence_end": 0.5,
                "eclipse_profile_id": "partial_eclipse",
            },
        ],
    )
    write_eclipse_profiles(
        paths,
        [
            {"eclipse_profile_id": "none", "profile_time_s": 0.0, "transmission_fraction": 1.0},
            {"eclipse_profile_id": "none", "profile_time_s": 600.0, "transmission_fraction": 1.0},
            {
                "eclipse_profile_id": "partial_eclipse",
                "profile_time_s": 0.0,
                "transmission_fraction": 1.0,
            },
            {
                "eclipse_profile_id": "partial_eclipse",
                "profile_time_s": 200.0,
                "transmission_fraction": 0.4,
            },
            {
                "eclipse_profile_id": "partial_eclipse",
                "profile_time_s": 400.0,
                "transmission_fraction": 0.4,
            },
            {
                "eclipse_profile_id": "partial_eclipse",
                "profile_time_s": 600.0,
                "transmission_fraction": 1.0,
            },
        ],
    )
    write_observation_queries(
        paths,
        [
            {
                "observation_id": "obs_d",
                "case_id": "case_diurnal",
                "time_s": 300.0,
                "band_id": "band_8um",
            },
            {
                "observation_id": "obs_e",
                "case_id": "case_eclipse",
                "time_s": 300.0,
                "band_id": "band_8um",
            },
        ],
    )
    clear_inversions(paths)
    mutate_all_materials(
        paths,
        contact_conductivity_w_m_k=0.1,
        heat_capacity_c1_j_kg_k2=0.0,
        heat_capacity_c2_j_kg_k3=0.0,
        conductivity_depth_gradient_per_m=0.0,
        radiative_conductivity_w_m_k4=0.0,
        surface_albedo=0.2,
        surface_emissivity=0.9,
        density_kg_m3=1000.0,
        heat_capacity_c0_j_kg_k=600.0,
    )

    before = expect_success(paths, tmp_path / "before.json")
    before_ref = build_report(paths.data_dir)

    set_eclipse_point(paths, "partial_eclipse", 200.0, 0.05)
    set_eclipse_point(paths, "partial_eclipse", 400.0, 0.05)
    after = expect_success(paths, tmp_path / "after.json")
    after_ref = build_report(paths.data_dir)

    before_d = radiometer_map(before)["obs_d"]
    after_d = radiometer_map(after)["obs_d"]
    before_e = radiometer_map(before)["obs_e"]
    after_e = radiometer_map(after)["obs_e"]
    assert_close(
        float(after_d["brightness_temperature_k"]),
        float(before_d["brightness_temperature_k"]),
        abs_tol=1.0e-4,
        label="diurnal locality",
    )
    assert abs(
        float(after_e["brightness_temperature_k"]) - float(before_e["brightness_temperature_k"])
    ) > 0.05
    assert_close(
        float(after_d["brightness_temperature_k"]),
        float(radiometer_map(after_ref)["obs_d"]["brightness_temperature_k"]),
        abs_tol=1.0e-3,
        label="locality diurnal ref",
    )
    assert_close(
        float(after_e["brightness_temperature_k"]),
        float(radiometer_map(after_ref)["obs_e"]["brightness_temperature_k"]),
        abs_tol=1.0e-3,
        label="locality eclipse ref",
    )
    assert_close(
        float(before_e["brightness_temperature_k"]),
        float(radiometer_map(before_ref)["obs_e"]["brightness_temperature_k"]),
        abs_tol=1.0e-3,
        label="before eclipse ref",
    )


def test_25_complete_report(tmp_path: Path) -> None:
    """Validate every public report section, keys, sorting, and summary aggregation."""
    paths = copy_fixture_tree(tmp_path)
    clear_inversions(paths)
    mutate_all_materials(paths, contact_conductivity_w_m_k=0.05)
    for case_id in ("case_diurnal", "case_eclipse", "case_gradient"):
        set_illumination_field(paths, case_id, "maximum_spinup_cycles", 15)
        set_illumination_field(paths, case_id, "spinup_tolerance_k", 2.0)
    report = expect_success(paths, tmp_path / "report.json")
    ref = build_report(paths.data_dir)

    required_sections = {
        "time_step_rows",
        "temperature_rows",
        "surface_flux_rows",
        "radiometer_rows",
        "inverse_fit_rows",
        "solver_diagnostics",
        "summary",
    }
    assert set(report) == required_sections
    assert set(ref) == required_sections

    time_step_fields = {
        "case_id",
        "step_index",
        "start_time_s",
        "end_time_s",
        "nonlinear_iterations",
        "maximum_residual_w_m2",
        "converged",
    }
    temperature_fields = {
        "case_id",
        "observation_id",
        "time_s",
        "cell_index",
        "depth_center_m",
        "temperature_k",
    }
    flux_fields = {
        "case_id",
        "step_index",
        "end_time_s",
        "absorbed_solar_flux_w_m2",
        "emitted_thermal_flux_w_m2",
        "conductive_flux_down_w_m2",
        "geothermal_flux_up_w_m2",
        "stored_energy_change_j_m2",
        "net_boundary_energy_j_m2",
        "energy_residual_j_m2",
    }
    radiometer_fields = {
        "observation_id",
        "case_id",
        "time_s",
        "band_id",
        "surface_temperature_k",
        "band_radiance_w_m2_sr",
        "brightness_temperature_k",
    }
    diagnostic_fields = {
        "case_id",
        "spinup_cycles",
        "final_spinup_difference_k",
        "report_step_count",
        "maximum_step_residual_w_m2",
        "minimum_temperature_k",
        "maximum_temperature_k",
        "all_values_finite",
    }
    summary_fields = {
        "case_count",
        "observation_count",
        "radiometer_row_count",
        "inverse_fit_count",
        "converged_inverse_fit_count",
        "minimum_surface_temperature_k",
        "maximum_surface_temperature_k",
        "maximum_brightness_temperature_k",
        "minimum_inversion_objective",
        "maximum_absolute_energy_residual_j_m2",
    }

    assert report["time_step_rows"]
    assert report["temperature_rows"]
    assert report["surface_flux_rows"]
    assert report["radiometer_rows"]
    assert report["solver_diagnostics"]
    assert report["inverse_fit_rows"] == []

    assert set(report["time_step_rows"][0]) == time_step_fields
    assert set(report["temperature_rows"][0]) == temperature_fields
    assert set(report["surface_flux_rows"][0]) == flux_fields
    assert set(report["radiometer_rows"][0]) == radiometer_fields
    assert set(report["solver_diagnostics"][0]) == diagnostic_fields
    assert set(report["summary"]) == summary_fields

    def sort_key_time(row: Mapping[str, Any]) -> Tuple[Any, ...]:
        return (row["case_id"], int(row["step_index"]))

    def sort_key_temp(row: Mapping[str, Any]) -> Tuple[Any, ...]:
        return (row["case_id"], row["observation_id"], int(row["cell_index"]))

    def sort_key_rad(row: Mapping[str, Any]) -> Tuple[Any, ...]:
        return (row["observation_id"],)

    assert report["time_step_rows"] == sorted(report["time_step_rows"], key=sort_key_time)
    assert report["temperature_rows"] == sorted(report["temperature_rows"], key=sort_key_temp)
    assert report["radiometer_rows"] == sorted(report["radiometer_rows"], key=sort_key_rad)

    summary = report["summary"]
    query_ids = {row["observation_id"] for row in read_csv(paths.observation_queries)}
    report_obs_ids = {row["observation_id"] for row in report["radiometer_rows"]}
    assert report_obs_ids == query_ids
    temp_obs_ids = {row["observation_id"] for row in report["temperature_rows"]}
    assert temp_obs_ids == query_ids
    for case_id in ("case_diurnal", "case_eclipse", "case_gradient"):
        steps = sorted(
            int(row["step_index"])
            for row in report["time_step_rows"]
            if row["case_id"] == case_id
        )
        assert steps == list(range(len(steps)))
        flux_steps = sorted(
            int(row["step_index"])
            for row in report["surface_flux_rows"]
            if row["case_id"] == case_id
        )
        assert flux_steps == list(range(len(flux_steps)))
    assert int(summary["case_count"]) == 3
    assert int(summary["observation_count"]) == len(query_ids)
    assert int(summary["radiometer_row_count"]) == len(report["radiometer_rows"])
    assert int(summary["inverse_fit_count"]) == 0
    assert int(summary["converged_inverse_fit_count"]) == 0
    assert_close(
        float(summary["maximum_absolute_energy_residual_j_m2"]),
        float(ref["summary"]["maximum_absolute_energy_residual_j_m2"]),
        abs_tol=1.0e-4,
        label="summary energy",
    )
    assert_close(
        float(summary["maximum_brightness_temperature_k"]),
        float(ref["summary"]["maximum_brightness_temperature_k"]),
        abs_tol=1.0e-3,
        label="summary Tb",
    )

    got_temp = temperature_map(report)
    exp_temp = temperature_map(ref)
    assert_same_keys(got_temp, exp_temp, label="complete temps")
    for key, expected in exp_temp.items():
        assert_close(got_temp[key], expected, abs_tol=1.0e-3, label=f"complete T{key}")

    got_rad = radiometer_map(report)
    exp_rad = radiometer_map(ref)
    assert_same_keys(got_rad, exp_rad, label="complete rad")
    for obs_id, row in exp_rad.items():
        assert_close(
            float(got_rad[obs_id]["brightness_temperature_k"]),
            float(row["brightness_temperature_k"]),
            abs_tol=1.0e-3,
            label=f"complete Tb {obs_id}",
        )


def test_26_deterministic_rerun(tmp_path: Path) -> None:
    """Two clean identical fixture copies must produce byte-identical reports."""
    first_root = tmp_path / "run_a"
    second_root = tmp_path / "run_b"
    first = copy_fixture_tree(first_root)
    second = copy_fixture_tree(second_root)
    for paths in (first, second):
        configure_micro_case(
            paths,
            case_id="case_det",
            period_s=400.0,
            time_step_s=100.0,
            solar_flux_w_m2=400.0,
            geothermal_flux_w_m2=0.02,
            cos_incidence=0.4,
            cell_count=2,
            thickness_m=0.15,
            initial_temperature_k=230.0,
            maximum_spinup_cycles=10,
            spinup_tolerance_k=1.5,
            observation_times_s=[200.0, 400.0],
            material_overrides={
                "surface_albedo": 0.15,
                "surface_emissivity": 0.9,
                "heat_capacity_c1_j_kg_k2": 0.0,
                "heat_capacity_c2_j_kg_k3": 0.0,
                "conductivity_depth_gradient_per_m": 0.0,
                "radiative_conductivity_w_m_k4": 0.0,
                "contact_conductivity_w_m_k": 0.1,
                "density_kg_m3": 1000.0,
                "heat_capacity_c0_j_kg_k": 600.0,
            },
        )
    out_a = first_root / "report.json"
    out_b = second_root / "report.json"
    report_a = expect_success(first, out_a)
    report_b = expect_success(second, out_b)
    bytes_a = out_a.read_bytes()
    bytes_b = out_b.read_bytes()
    assert bytes_a == bytes_b
    assert report_a == report_b
    # Also agree with the independent reference on the same inputs.
    ref = build_report(first.data_dir)
    assert_close(
        float(report_a["summary"]["maximum_brightness_temperature_k"]),
        float(ref["summary"]["maximum_brightness_temperature_k"]),
        abs_tol=1.0e-3,
        label="deterministic summary",
    )
