import copy
import csv
import json
import math
import re
import subprocess
from pathlib import Path

import numpy as np
import pytest

APP = Path("/app")
OUT = APP / "output"
OUTPUT_FILES = (
    "baseline_final.csv",
    "risk_summary.json",
    "well_exceedance_probabilities.csv",
)


@pytest.fixture(scope="session", autouse=True)
def restore_site_config():
    cfg_path = APP / "site_config.json"
    original = cfg_path.read_text()
    yield
    cfg_path.write_text(original)


@pytest.fixture(scope="session")
def original_config():
    return load_config()


def write_config(cfg):
    (APP / "site_config.json").write_text(json.dumps(cfg, indent=2) + "\n")


def run_model(config=None):
    if config is not None:
        write_config(config)
    OUT.mkdir(exist_ok=True)
    for name in OUTPUT_FILES:
        path = OUT / name
        if path.exists():
            path.unlink()
    r = subprocess.run(
        ["node", str(APP / "run_risk_study.js")],
        cwd=str(APP), capture_output=True, text=True, timeout=600,
    )
    assert r.returncode == 0, (
        f"model exited {r.returncode}\nSTDOUT:\n{r.stdout}\nSTDERR:\n{r.stderr}"
    )


def load_config():
    return json.loads((APP / "site_config.json").read_text())


def load_summary():
    return json.loads((OUT / "risk_summary.json").read_text())


def load_exceedance():
    rows = {}
    with (OUT / "well_exceedance_probabilities.csv").open() as f:
        for row in csv.DictReader(f):
            rows[row["well_id"]] = float(row["exceedance_probability"])
    return rows


def load_exceedance_rows():
    with (OUT / "well_exceedance_probabilities.csv").open() as f:
        return {row["well_id"]: row for row in csv.DictReader(f)}


def load_grid():
    return np.loadtxt(OUT / "baseline_final.csv", delimiter=",")


def run_node_json(script):
    r = subprocess.run(
        ["node", "-e", script],
        cwd=str(APP), capture_output=True, text=True, timeout=60,
    )
    assert r.returncode == 0, (
        f"node script exited {r.returncode}\nSTDOUT:\n{r.stdout}\nSTDERR:\n{r.stderr}"
    )
    return json.loads(r.stdout)


def grid_axes(cfg):
    dx = cfg["Lx"] / cfg["nx"]
    dy = cfg["Ly"] / cfg["ny"]
    return dx, dy


def concentration_moments(cfg, C):
    dx, dy = grid_axes(cfg)
    xs = (np.arange(cfg["nx"]) + 0.5) * dx
    ys = (np.arange(cfg["ny"]) + 0.5) * dy
    XX, YY = np.meshgrid(xs, ys)
    m = C.sum()
    cx = (C * XX).sum() / m
    cy = (C * YY).sum() / m
    vxx = (C * (XX - cx) ** 2).sum() / m
    vyy = (C * (YY - cy) ** 2).sum() / m
    vxy = (C * (XX - cx) * (YY - cy)).sum() / m
    return cx, cy, vxx, vyy, vxy


def mean_params(cfg):
    return {
        "vx": cfg["vx_mean"],
        "vy": cfg["vy_mean"],
        "alphaL": cfg["alphaL_mean"],
        "alphaT": cfg["alphaT_mean"],
        "Dm": cfg["Dm"],
        "rho_b": cfg["rho_b"],
        "Kd": cfg["Kd"],
        "theta": cfg["theta"],
        "lambda": cfg["lambda_mean"],
    }


def clamp_idx(v, n):
    return min(max(int(math.floor(v + 0.5)), 0), n - 1)


def source_indices(cfg):
    dx, dy = grid_axes(cfg)
    si = clamp_idx(cfg["source_x"] / dx - 0.5, cfg["nx"])
    sj = clamp_idx(cfg["source_y"] / dy - 0.5, cfg["ny"])
    return sj, si


def grid_well_values(cfg, C):
    dx, dy = grid_axes(cfg)
    return np.array([bilinear(C, w["x"], w["y"], dx, dy) for w in cfg["wells"]])


def simulate_module(p, cfg):
    dx, dy = grid_axes(cfg)
    g = {"nx": cfg["nx"], "ny": cfg["ny"], "dx": dx, "dy": dy}
    script = f"""
const {{ simulate }} = require('/app/simulate.js');
const p = {json.dumps(p)};
const g = {json.dumps(g)};
const cfg = {json.dumps(cfg)};
const result = simulate(p, g, cfg);
console.log(JSON.stringify({{grid: result[0], wells: result[1]}}));
"""
    data = run_node_json(script)
    return np.array(data["grid"], dtype=float), np.array(data["wells"], dtype=float)


def assert_close(actual, expected, *, rtol=1e-7, atol=1e-7, label="value"):
    assert math.isclose(actual, expected, rel_tol=rtol, abs_tol=atol), (
        f"{label}: got {actual}, expected {expected}"
    )


def bilinear(C, wx, wy, dx, dy):
    ny, nx = C.shape
    gx = wx / dx - 0.5
    gy = wy / dy - 0.5
    i0 = int(np.floor(gx))
    j0 = int(np.floor(gy))
    fx = gx - i0
    fy = gy - j0
    i0 = min(max(i0, 0), nx - 2)
    j0 = min(max(j0, 0), ny - 2)
    if wx / dx - 0.5 < 0:
        fx = 0.0
    if wx / dx - 0.5 > nx - 2:
        fx = 1.0
    if wy / dy - 0.5 < 0:
        fy = 0.0
    if wy / dy - 0.5 > ny - 2:
        fy = 1.0
    return (
        (1 - fx) * (1 - fy) * C[j0, i0]
        + fx * (1 - fy) * C[j0, i0 + 1]
        + (1 - fx) * fy * C[j0 + 1, i0]
        + fx * fy * C[j0 + 1, i0 + 1]
    )


@pytest.fixture(scope="module")
def study(original_config):
    run_model(original_config)
    return original_config


def test_app_implementation_stays_javascript_only():
    """Verify the app implementation does not add non-JavaScript source files."""
    allowed_suffixes = {".js", ".json", ".md"}
    bad_files = []
    for path in APP.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(APP)
        if "output" in relative.parts:
            continue
        if path.suffix.lower() not in allowed_suffixes:
            bad_files.append(str(relative))
    assert not bad_files, f"non-JavaScript implementation files found: {bad_files}"


def test_driver_keeps_reusable_module_wiring():
    """Verify the driver still imports the reusable simulation and sampler modules."""
    src = (APP / "run_risk_study.js").read_text()
    assert "require('./simulate')" in src or 'require("./simulate")' in src
    assert (
        "require('./sample_aquifer_params')" in src
        or 'require("./sample_aquifer_params")' in src
    )
    assert re.search(r"\bsimulate\s*\(", src), "run_risk_study.js does not call simulate"
    assert re.search(
        r"\bsample_aquifer_params\s*\(", src
    ), "run_risk_study.js does not call sample_aquifer_params"
    assert "function simulate" not in src
    assert "function sample_aquifer_params" not in src


def test_outputs_exist(study):
    """Verify the driver writes all required output files."""
    for name in OUTPUT_FILES:
        p = OUT / name
        assert p.exists() and p.stat().st_size > 0, f"missing/empty: {name}"


def test_output_metadata_matches_config(study):
    """Verify summary fields and exceedance CSV coordinates match site_config.json."""
    cfg = study
    summary = load_summary()
    assert summary["seed"] == cfg["seed"]
    assert summary["n_samples"] == cfg["n_samples"]
    assert summary["exceedance_threshold"] == cfg["exceedance_threshold"]
    well_ids = [w["id"] for w in cfg["wells"]]
    assert [w["id"] for w in summary["baseline_wells"]] == well_ids
    assert [w["id"] for w in summary["wells"]] == well_ids
    rows = load_exceedance_rows()
    assert set(rows) == set(well_ids)
    for well in cfg["wells"]:
        row = rows[well["id"]]
        assert_close(float(row["x"]), well["x"], label=f"{well['id']} x")
        assert_close(float(row["y"]), well["y"], label=f"{well['id']} y")


def test_baseline_bounded(study):
    """Verify the baseline grid is finite, nonnegative, bounded, and nonempty."""
    cfg = study
    C = load_grid()
    assert C.shape == (cfg["ny"], cfg["nx"]), f"grid shape {C.shape}"
    assert np.all(np.isfinite(C)), "baseline grid has non-finite values"
    assert C.min() >= -1e-6, "baseline has negative concentrations"
    assert C.max() <= cfg["source_conc"] + 1e-3, "baseline exceeds the source (unstable)"
    assert C.max() > 0, "baseline plume is empty"


def test_dispersion_is_flow_oriented(study):
    """Verify the baseline plume spreads along the diagonal flow direction."""
    cfg = study
    _, _, vxx, vyy, vxy = concentration_moments(cfg, load_grid())
    corr = vxy / math.sqrt(vxx * vyy)
    assert corr > 0.35, f"plume shear correlation {corr:.3f} too low; cross-term missing"


def test_retardation_slows_plume(study):
    """Verify the baseline plume travels downgradient without outrunning retardation."""
    cfg = study
    C = load_grid()
    cx, cy, *_ = concentration_moments(cfg, C)
    dist = math.hypot(cx - cfg["source_x"], cy - cfg["source_y"])
    assert dist > 5, f"plume did not travel (centroid {dist:.1f} m from source)"
    assert dist < 40, f"plume travelled too far ({dist:.1f} m); retardation missing"


def test_well_reading_is_bilinear(study):
    """Verify baseline well values are interpolated from the final grid."""
    cfg = study
    dx, dy = grid_axes(cfg)
    C = load_grid()
    reported = {w["id"]: float(w["value"]) for w in load_summary()["baseline_wells"]}
    for well in cfg["wells"]:
        exp = bilinear(C, well["x"], well["y"], dx, dy)
        got = reported[well["id"]]
        assert abs(got - exp) <= 1e-3 + 1e-3 * abs(exp), (
            f"{well['id']} value {got} is not bilinear interpolation ({exp})"
        )


def test_percentiles_monotonic_and_finite(study):
    """Verify Monte Carlo percentile summaries are finite and ordered."""
    summary = load_summary()
    assert 0 <= summary["n_discarded"] < summary["n_samples"]
    for w in load_summary()["wells"]:
        for key in ("p05", "p50", "p95"):
            assert np.isfinite(w[key]), f"{w['id']} {key} not finite"
        assert w["p95"] >= w["p50"] >= w["p05"], f"{w['id']} percentiles not monotonic"


def test_exceedance_in_unit_range(study):
    """Verify exceedance probabilities are valid probabilities."""
    for well_id, prob in load_exceedance().items():
        assert 0.0 <= prob <= 1.0, f"{well_id} exceedance {prob} out of [0,1]"


def test_mc_has_spread(study):
    """Verify the configured uncertain study changes downstream well readings."""
    dn = next(w for w in load_summary()["wells"] if w["id"] == "MW-downstream")
    assert dn["p95"] > dn["p05"], "no spread across Monte Carlo samples"


def test_downstream_higher_risk_than_background(study):
    """Verify the downgradient well is riskier than the background well."""
    probs = load_exceedance()
    assert probs["MW-downstream"] > probs["MW-background"], (
        f"downstream {probs['MW-downstream']} not > background {probs['MW-background']}"
    )


def test_step_transport_has_physical_effect(study):
    """Verify one transport step advects or disperses concentration on the grid."""
    C = np.array([
        [0.0, 0.0, 0.0, 0.0, 0.0],
        [0.0, 0.0, 0.0, 0.0, 0.0],
        [0.0, 0.0, 12.0, 0.0, 0.0],
        [0.0, 0.0, 0.0, 0.0, 0.0],
        [0.0, 0.0, 0.0, 0.0, 0.0],
    ])
    p = {
        "vx": 0.27,
        "vy": 0.19,
        "alphaL": 2.4,
        "alphaT": 0.18,
        "Dm": 0.015,
        "rho_b": 1.55,
        "Kd": 0.21,
        "theta": 0.37,
        "lambda": 0.006,
    }
    g = {"nx": 5, "ny": 5, "dx": 2.0, "dy": 1.5}
    dt = 0.18
    script = f"""
const {{ step_transport }} = require('/app/step_transport.js');
const C = {json.dumps(C.tolist())};
const p = {json.dumps(p)};
const g = {json.dumps(g)};
console.log(JSON.stringify(step_transport(C, p, g, {dt})));
"""
    got = np.array(run_node_json(script), dtype=float)
    assert got.shape == C.shape
    assert np.all(np.isfinite(got))
    assert not np.allclose(got, C), "step_transport left the grid unchanged"
    assert got[2, 3] > 0 or got[3, 2] > 0, "concentration did not move downgradient"
    assert got[2, 2] < C[2, 2], "source cell did not lose mass during a raw step"


def test_simulate_module_produces_plausible_plume(study):
    """Verify simulate.js directly produces a bounded downgradient plume."""
    cfg = copy.deepcopy(study)
    cfg.update({
        "Lx": 72.0,
        "Ly": 64.0,
        "nx": 36,
        "ny": 32,
        "end_time": 120.0,
        "nsteps": 240,
        "source_x": 14.4,
        "source_y": 16.0,
        "source_conc": 70.0,
        "vx_mean": 0.24,
        "vy_mean": 0.16,
        "alphaL_mean": 3.2,
        "alphaT_mean": 0.22,
        "Dm": 0.018,
        "rho_b": 1.45,
        "Kd": 0.18,
        "theta": 0.36,
        "lambda_mean": 0.004,
        "wells": [
            {"id": "MW-module-down", "x": 29.5, "y": 26.0},
            {"id": "MW-module-side", "x": 18.0, "y": 44.0},
        ],
    })
    got_grid, got_wells = simulate_module(mean_params(cfg), cfg)
    assert got_grid.shape == (cfg["ny"], cfg["nx"])
    assert np.all(np.isfinite(got_grid))
    assert got_grid.min() >= -1e-6
    assert got_grid.max() <= cfg["source_conc"] + 1e-3
    sj, si = source_indices(cfg)
    assert got_grid[sj, si] >= cfg["source_conc"] - 1e-6
    assert np.allclose(got_wells, grid_well_values(cfg, got_grid), rtol=1e-3, atol=1e-3)
    cx, cy, vxx, vyy, vxy = concentration_moments(cfg, got_grid)
    assert cx > cfg["source_x"] + 5, f"plume centroid x={cx:.2f} did not move downgradient"
    assert cy > cfg["source_y"] + 3, f"plume centroid y={cy:.2f} did not move downgradient"
    assert math.hypot(cx - cfg["source_x"], cy - cfg["source_y"]) < 35
    assert vxy / math.sqrt(vxx * vyy) > 0.2, "plume does not show diagonal spreading"
    assert got_wells[0] > got_wells[1], "downgradient module well is not above side well"


def test_sampler_uses_seed_and_cov(study):
    """Verify sampled parameters are positive, variable, mean-scaled, and reproducible."""
    cfg = copy.deepcopy(study)
    cfg.update({"seed": 24681357, "cov": 0.25})
    script = f"""
const {{ sample_aquifer_params }} = require('/app/sample_aquifer_params.js');
const cfg = {json.dumps(cfg)};
const rows = [];
for (let k = 0; k < 80; k++) rows.push(sample_aquifer_params(cfg, k));
console.log(JSON.stringify(rows));
"""
    first = run_node_json(script)
    second = run_node_json(script)
    assert first == second, "sampler is not reproducible for the configured seed"
    for key in ("vx", "vy", "alphaL", "alphaT", "lambda"):
        values = np.array([row[key] for row in first], dtype=float)
        assert np.all(values > 0), f"{key} samples must stay physically valid"
        assert values.std() > 0.01 * cfg[f"{key}_mean"], f"{key} ignores cov"
        assert_close(values.mean(), cfg[f"{key}_mean"], rtol=0.35, atol=0, label=f"{key} mean")


def test_custom_zero_cov_case_uses_final_grid_consistently(study, original_config):
    """Verify a changed zero-uncertainty site reports final-grid values consistently."""
    cfg = copy.deepcopy(original_config)
    cfg.update({
        "seed": 314159,
        "n_samples": 7,
        "Lx": 84.0,
        "Ly": 72.0,
        "nx": 42,
        "ny": 36,
        "end_time": 150.0,
        "nsteps": 300,
        "source_x": 16.4,
        "source_y": 19.2,
        "source_conc": 80.0,
        "vx_mean": 0.26,
        "vy_mean": 0.18,
        "alphaL_mean": 3.6,
        "alphaT_mean": 0.25,
        "Dm": 0.02,
        "rho_b": 1.4,
        "Kd": 0.16,
        "theta": 0.35,
        "lambda_mean": 0.0035,
        "cov": 0.0,
        "exceedance_threshold": 8.0,
        "wells": [
            {"id": "MW-custom-down", "x": 35.7, "y": 32.4},
            {"id": "MW-custom-side", "x": 18.1, "y": 54.6},
            {"id": "MW-custom-tail", "x": 46.3, "y": 40.2},
        ],
    })
    try:
        run_model(cfg)
        got_grid = load_grid()
        assert got_grid.shape == (cfg["ny"], cfg["nx"])
        assert np.all(np.isfinite(got_grid))
        assert got_grid.min() >= -1e-6
        assert got_grid.max() <= cfg["source_conc"] + 1e-3
        sj, si = source_indices(cfg)
        assert got_grid[sj, si] >= cfg["source_conc"] - 1e-6
        cx, cy, vxx, vyy, vxy = concentration_moments(cfg, got_grid)
        assert cx > cfg["source_x"] + 5, f"plume centroid x={cx:.2f} did not move downgradient"
        assert cy > cfg["source_y"] + 3, f"plume centroid y={cy:.2f} did not move downgradient"
        assert math.hypot(cx - cfg["source_x"], cy - cfg["source_y"]) < 40
        assert vxy / math.sqrt(vxx * vyy) > 0.2, "plume does not show diagonal spreading"

        summary = load_summary()
        assert summary["seed"] == cfg["seed"]
        assert summary["n_samples"] == cfg["n_samples"]
        assert summary["n_discarded"] == 0
        assert summary["exceedance_threshold"] == cfg["exceedance_threshold"]
        reported = {w["id"]: float(w["value"]) for w in summary["baseline_wells"]}
        percentiles = {w["id"]: w for w in summary["wells"]}
        probabilities = load_exceedance()
        rows = load_exceedance_rows()
        expected_wells = grid_well_values(cfg, got_grid)

        for well, expected in zip(cfg["wells"], expected_wells):
            well_id = well["id"]
            assert_close(float(rows[well_id]["x"]), well["x"], label=f"{well_id} x")
            assert_close(float(rows[well_id]["y"]), well["y"], label=f"{well_id} y")
            assert_close(reported[well_id], expected, rtol=1e-3, atol=1e-3, label=well_id)
            for key in ("p05", "p50", "p95"):
                assert_close(
                    percentiles[well_id][key], expected,
                    rtol=1e-3, atol=1e-3, label=f"{well_id} {key}",
                )
            expected_prob = 1.0 if expected > cfg["exceedance_threshold"] else 0.0
            assert_close(
                probabilities[well_id], expected_prob,
                rtol=0.0, atol=1e-12, label=f"{well_id} exceedance probability",
            )
    finally:
        write_config(original_config)


def test_reproducible_summary(original_config):
    """Verify the configured seed makes repeated risk summaries identical."""
    run_model(original_config)
    first = load_summary()
    run_model(original_config)
    second = load_summary()
    assert first == second, "summary not reproducible for the configured seed"
