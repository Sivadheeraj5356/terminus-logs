"""Verifier tests for the GammaSpec TypeScript audit task."""

from __future__ import annotations

import json
import math
import os
import subprocess
import time
from collections.abc import Callable, Generator
from pathlib import Path
from typing import Any

import pytest
import requests

APP_DIR = Path("/app")
PORT = 32187
BASE_URL = f"http://127.0.0.1:{PORT}"
CALIBRATION_PATH = APP_DIR / "data" / "calibration.gamma.json"
MATRIX_PATH = APP_DIR / "output" / "compliance_matrix.json"


def _load_calibration() -> dict[str, Any]:
    with CALIBRATION_PATH.open() as handle:
        return json.load(handle)


def _channel_to_energy(channel: float, calibration: dict[str, Any]) -> float:
    poly = calibration["channelPolynomial"]
    return poly["offset"] + poly["slope"] * channel + poly["quadratic"] * channel * channel


def _gaussian(energy: float, center: float, sigma: float) -> float:
    return math.exp(-0.5 * ((energy - center) / sigma) ** 2)


def _tail_basis(energy: float, center: float, decay: float | None) -> float:
    if decay is None or energy > center:
        return 0.0
    return math.exp((energy - center) / decay)


def _solve_linear(matrix: list[list[float]], vector: list[float]) -> list[float]:
    size = len(vector)
    augmented = [row[:] + [vector[row_idx]] for row_idx, row in enumerate(matrix)]
    for col in range(size):
        pivot = max(range(col, size), key=lambda row: abs(augmented[row][col]))
        augmented[col], augmented[pivot] = augmented[pivot], augmented[col]
        divisor = augmented[col][col]
        assert abs(divisor) > 1e-14
        for idx in range(col, size + 1):
            augmented[col][idx] /= divisor
        for row in range(size):
            if row == col:
                continue
            factor = augmented[row][col]
            for idx in range(col, size + 1):
                augmented[row][idx] -= factor * augmented[col][idx]
    return [augmented[row][size] for row in range(size)]


def _invert_matrix(matrix: list[list[float]]) -> list[list[float]]:
    size = len(matrix)
    inverse = [[0.0 for _ in range(size)] for _ in range(size)]
    for col in range(size):
        rhs = [0.0 for _ in range(size)]
        rhs[col] = 1.0
        solved = _solve_linear(matrix, rhs)
        for row in range(size):
            inverse[row][col] = solved[row]
    return inverse


def _normalization(payload: dict[str, Any]) -> dict[str, float | bool]:
    live = float(payload.get("liveTimeSec", 1.0))
    real = float(payload.get("realTimeSec", live))
    background = payload.get("background")
    scale = live / float(background["liveTimeSec"]) if background else 0.0
    return {
        "liveTimeSec": live,
        "realTimeSec": real,
        "deadTimeCorrection": real / live,
        "backgroundSubtracted": bool(background),
        "backgroundScale": scale,
    }


def _prepared_fit(payload: dict[str, Any]) -> dict[str, Any]:
    calibration = _load_calibration()
    peak = calibration["peaks"][payload["isotope"]]
    channels = payload["channels"]
    counts = payload["counts"]
    background = payload.get("background")
    info = _normalization(payload)
    live = float(info["liveTimeSec"])
    dead = float(info["deadTimeCorrection"])
    scale = float(info["backgroundScale"])
    energies = [_channel_to_energy(channel, calibration) for channel in channels]
    center = peak["energyKeV"]
    sigma = peak["sigmaKeV"]
    decay = peak.get("tailDecayKeV")
    roi_indices = [
        idx
        for idx, energy in enumerate(energies)
        if abs(energy - center) <= peak["roiHalfWidthKeV"]
    ]
    assert len(roi_indices) > 4

    rows: list[list[float]] = []
    observed: list[float] = []
    weights: list[float] = []
    for idx in roi_indices:
        energy = energies[idx]
        row = [
            _gaussian(energy, center, sigma),
            _tail_basis(energy, center, decay),
            1.0,
            energy - center,
        ]
        bg_count = background["counts"][idx] if background else 0.0
        net_count = counts[idx] - scale * bg_count
        observed_rate = net_count * dead / live
        variance = (
            max(counts[idx], 1.0)
            + (scale * scale * max(bg_count, 1.0) if background else 0.0)
            + calibration["readNoiseVariance"]
        ) * (dead / live) ** 2
        rows.append(row)
        observed.append(observed_rate)
        weights.append(1.0 / variance)
    return {
        "calibration": calibration,
        "peak": peak,
        "energies": energies,
        "roiIndices": roi_indices,
        "rows": rows,
        "observed": observed,
        "weights": weights,
        "normalization": info,
    }


def _fit_from_prepared(
    prepared: dict[str, Any],
    observed: list[float] | None = None,
) -> dict[str, Any]:
    rows = prepared["rows"]
    y = prepared["observed"] if observed is None else observed
    weights = prepared["weights"]
    size = 4
    normal = [[0.0 for _ in range(size)] for _ in range(size)]
    rhs = [0.0 for _ in range(size)]
    for row, weight, value in zip(rows, weights, y, strict=True):
        for r_idx in range(size):
            rhs[r_idx] += row[r_idx] * weight * value
            for c_idx in range(size):
                normal[r_idx][c_idx] += row[r_idx] * weight * row[c_idx]
    beta = _solve_linear(normal, rhs)
    fitted = [sum(row[col] * beta[col] for col in range(size)) for row in rows]
    residuals = [value - fit for value, fit in zip(y, fitted, strict=True)]
    degrees = len(rows) - size
    reduced_chi = sum(
        weight * residual * residual for weight, residual in zip(weights, residuals, strict=True)
    ) / degrees
    inverse = _invert_matrix(normal)
    covariance = [[value * reduced_chi for value in row] for row in inverse]
    return {
        "beta": beta,
        "covariance": covariance,
        "reducedChiSquare": reduced_chi,
        "degreesOfFreedom": degrees,
        "residuals": residuals,
        "fittedRates": fitted,
    }


def _expected_fit(payload: dict[str, Any]) -> dict[str, Any]:
    prepared = _prepared_fit(payload)
    solved = _fit_from_prepared(prepared)
    indices = prepared["roiIndices"]
    energies = prepared["energies"]
    channels = payload["channels"]
    info = prepared["normalization"]
    flags = ["tail-model-applied"]
    if info["backgroundSubtracted"]:
        flags.append("background-subtracted")
    if float(info["deadTimeCorrection"]) > 1.0005:
        flags.append("dead-time-corrected")
    if solved["reducedChiSquare"] > 3.0:
        flags.append("high-reduced-chi-square")
    return {
        **prepared,
        **solved,
        "roiEnergyMin": min(energies[idx] for idx in indices),
        "roiEnergyMax": max(energies[idx] for idx in indices),
        "roiChannelMin": min(channels[idx] for idx in indices),
        "roiChannelMax": max(channels[idx] for idx in indices),
        "qualityFlags": flags,
    }


def _mulberry32(seed: int) -> Callable[[], float]:
    state = seed & 0xFFFFFFFF

    def rng() -> float:
        nonlocal state
        state = (state + 0x6D2B79F5) & 0xFFFFFFFF
        value = state
        value = ((value ^ (value >> 15)) * (value | 1)) & 0xFFFFFFFF
        value ^= (value + (((value ^ (value >> 7)) * (value | 61)) & 0xFFFFFFFF)) & 0xFFFFFFFF
        return ((value ^ (value >> 14)) & 0xFFFFFFFF) / 4294967296

    return rng


def _percentile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def _expected_bootstrap(payload: dict[str, Any], seed: int, iterations: int) -> dict[str, Any]:
    prepared = _prepared_fit(payload)
    base = _fit_from_prepared(prepared)
    rng = _mulberry32(seed)
    residuals = base["residuals"]
    fitted = base["fittedRates"]
    amplitudes = []
    for _ in range(iterations):
        synthetic = []
        for fit_value in fitted:
            draw = min(int(rng() * len(residuals)), len(residuals) - 1)
            synthetic.append(fit_value + residuals[draw])
        amplitudes.append(_fit_from_prepared(prepared, synthetic)["beta"][0])
    return {
        "pointEstimate": base["beta"][0],
        "ci68": [_percentile(amplitudes, 0.16), _percentile(amplitudes, 0.84)],
        "ci95": [_percentile(amplitudes, 0.025), _percentile(amplitudes, 0.975)],
    }




def _hat_diagonal(prepared: dict[str, Any]) -> list[float]:
    rows = prepared["rows"]
    weights = prepared["weights"]
    size = len(rows[0])
    normal = [[0.0 for _ in range(size)] for _ in range(size)]
    for row, weight in zip(rows, weights, strict=True):
        for r_idx in range(size):
            for c_idx in range(size):
                normal[r_idx][c_idx] += row[r_idx] * weight * row[c_idx]
    inverse = _invert_matrix(normal)
    hat_values: list[float] = []
    for row, weight in zip(rows, weights, strict=True):
        inner = 0.0
        for r_idx in range(size):
            for c_idx in range(size):
                inner += row[r_idx] * inverse[r_idx][c_idx] * row[c_idx]
        hat_values.append(weight * inner)
    return hat_values


def _expected_diagnostics(payload: dict[str, Any]) -> dict[str, Any]:
    expected = _expected_fit(payload)
    weights = expected["weights"]
    residuals = expected["residuals"]
    fitted = expected["fittedRates"]
    observed = expected["observed"]
    hat_values = _hat_diagonal(expected)
    weight_sum = sum(weights)
    weighted_mean = sum(w * r for w, r in zip(weights, residuals, strict=True)) / weight_sum
    weighted_rms = math.sqrt(
        sum(w * r * r for w, r in zip(weights, residuals, strict=True)) / weight_sum
    )
    studentized = [
        abs(residual * math.sqrt(weight / max(1.0 - hat, 1e-12)))
        for residual, weight, hat in zip(residuals, weights, hat_values, strict=True)
    ]
    max_student = max(studentized)
    decision = (
        "review-required"
        if max_student > 2.8 or expected["reducedChiSquare"] > 3.0
        else "accepted"
    )
    flags = list(expected["qualityFlags"])
    if decision == "review-required":
        flags.append("residual-review")
    calibration = _load_calibration()
    return {
        "fit": expected,
        "normalizationRevision": calibration["normalizationRevision"],
        "integrals": {
            "observedRateSum": sum(observed),
            "fittedRateSum": sum(fitted),
            "absoluteResidualRateSum": sum(abs(value) for value in residuals),
        },
        "residualDiagnostics": {
            "weightedMeanRate": weighted_mean,
            "weightedRmsRate": weighted_rms,
            "maxAbsInternallyStudentized": max_student,
            "maxLeverage": max(hat_values),
            "reviewThreshold": 2.8,
        },
        "decision": decision,
        "qualityFlags": flags,
    }


def _aicc_from_expected(expected: dict[str, Any]) -> float:
    weighted_sse = expected["reducedChiSquare"] * expected["degreesOfFreedom"]
    n_points = len(expected["roiIndices"])
    k_params = 4
    aic = n_points * math.log(max(weighted_sse / n_points, 1e-12)) + 2 * k_params
    return aic + (2 * k_params * (k_params + 1)) / (n_points - k_params - 1)


def _expected_screen(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for isotope in payload["candidateIsotopes"]:
        spectrum = {**payload["spectrum"], "isotope": isotope}
        expected = _expected_fit(spectrum)
        rows.append({
            "isotope": isotope,
            "aicc": _aicc_from_expected(expected),
            "amplitude": expected["beta"][0],
            "reducedChiSquare": expected["reducedChiSquare"],
            "roi": {
                "count": len(expected["roiIndices"]),
                "channelMin": expected["roiChannelMin"],
                "channelMax": expected["roiChannelMax"],
                "energyMinKeV": expected["roiEnergyMin"],
                "energyMaxKeV": expected["roiEnergyMax"],
            },
            "qualityFlags": expected["qualityFlags"],
        })
    rows.sort(key=lambda item: (item["aicc"], item["isotope"]))
    best = rows[0]["aicc"]
    for idx, row in enumerate(rows, start=1):
        row["rank"] = idx
        row["deltaAicc"] = row["aicc"] - best
    return rows


def _make_spectrum(
    isotope: str = "Na22",
    *,
    live: float = 123.0,
    real: float = 129.5,
    with_background: bool = True,
    amplitude: float = 3.4,
    tail: float = 0.82,
    baseline: float = 0.31,
    slope: float = 0.0065,
) -> dict[str, Any]:
    calibration = _load_calibration()
    peak = calibration["peaks"][isotope]
    center = peak["energyKeV"]
    if isotope == "Na22":
        channels = list(range(244, 264))
    elif isotope == "Cs137":
        channels = list(range(322, 342))
    else:
        channels = list(range(575, 597))
    background_live = 300.0
    dead = real / live
    scale = live / background_live if with_background else 0.0
    background_counts: list[float] = []
    counts: list[float] = []
    for offset, channel in enumerate(channels):
        energy = _channel_to_energy(channel, calibration)
        bg_rate = 0.08 + 0.00035 * (energy - center) + 0.006 * math.cos(offset * 0.47)
        bg_count = max(1.0, bg_rate * background_live)
        target_rate = (
            amplitude * _gaussian(energy, center, peak["sigmaKeV"])
            + tail * _tail_basis(energy, center, peak.get("tailDecayKeV"))
            + baseline
            + slope * (energy - center)
        )
        residual_rate = 0.018 * math.sin(offset * 1.7) + (0.012 if offset % 5 == 0 else 0.0)
        raw_count = (target_rate + residual_rate) * live / dead + scale * bg_count
        background_counts.append(bg_count)
        counts.append(max(1.0, raw_count))
    payload: dict[str, Any] = {
        "channels": channels,
        "counts": counts,
        "isotope": isotope,
        "liveTimeSec": live,
        "realTimeSec": real,
    }
    if with_background:
        payload["background"] = {
            "counts": background_counts,
            "liveTimeSec": background_live,
            "label": f"{isotope}-night-background",
        }
    return payload


def _make_screen_spectrum() -> dict[str, Any]:
    calibration = _load_calibration()
    live = 142.0
    real = 151.0
    background_live = 420.0
    dead = real / live
    scale = live / background_live
    channels = list(range(238, 348))
    counts: list[float] = []
    background_counts: list[float] = []
    cs = calibration["peaks"]["Cs137"]
    na = calibration["peaks"]["Na22"]
    for offset, channel in enumerate(channels):
        energy = _channel_to_energy(channel, calibration)
        bg_rate = 0.055 + 0.00009 * (energy - 580.0) + 0.0035 * math.cos(offset * 0.31)
        bg_count = max(1.0, bg_rate * background_live)
        target_rate = (
            3.9 * _gaussian(energy, cs["energyKeV"], cs["sigmaKeV"])
            + 0.7 * _tail_basis(energy, cs["energyKeV"], cs.get("tailDecayKeV"))
            + 0.18 * _gaussian(energy, na["energyKeV"], na["sigmaKeV"])
            + 0.055 * _tail_basis(energy, na["energyKeV"], na.get("tailDecayKeV"))
            + 0.26
            - 0.0007 * (energy - cs["energyKeV"])
        )
        residual_rate = 0.014 * math.sin(offset * 0.83) + (0.018 if offset in {37, 82} else 0.0)
        counts.append(max(1.0, (target_rate + residual_rate) * live / dead + scale * bg_count))
        background_counts.append(bg_count)
    return {
        "channels": channels,
        "counts": counts,
        "liveTimeSec": live,
        "realTimeSec": real,
        "background": {
            "counts": background_counts,
            "liveTimeSec": background_live,
            "label": "wide-screen-background",
        },
    }


@pytest.fixture(scope="session")
def api_server() -> Generator[tuple[str, subprocess.Popen[str]], None, None]:
    """Build the TypeScript project and expose a live API server for endpoint checks."""
    build = subprocess.run(
        ["npm", "run", "build"],
        cwd=APP_DIR,
        text=True,
        capture_output=True,
        timeout=90,
        check=False,
    )
    assert build.returncode == 0, build.stdout + build.stderr
    env = os.environ.copy()
    env["PORT"] = str(PORT)
    process = subprocess.Popen(
        ["node", "dist/server.js"],
        cwd=APP_DIR,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        deadline = time.time() + 12
        last_error: Exception | None = None
        while time.time() < deadline:
            if process.poll() is not None:
                output = process.stdout.read() if process.stdout else ""
                raise AssertionError(f"server exited early with {process.returncode}: {output}")
            try:
                response = requests.get(f"{BASE_URL}/health", timeout=0.4)
                if response.status_code == 200 and response.json().get("ok") is True:
                    break
            except requests.RequestException as exc:
                last_error = exc
                time.sleep(0.2)
        else:
            raise AssertionError(f"server did not become healthy: {last_error}")
        yield BASE_URL, process
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def _assert_close(actual: float, expected: float, tolerance: float = 2e-5) -> None:
    assert math.isfinite(actual)
    assert math.isclose(actual, expected, rel_tol=2e-5, abs_tol=tolerance), (
        f"actual={actual} expected={expected}"
    )


def _assert_fit_matches(data: dict[str, Any], expected: dict[str, Any]) -> None:
    assert data["method"] == "poisson-readout-tail-wls-r4"
    assert data["weighting"] == "poisson_readout_live_rate_inverse_variance"
    assert data["calibrationApplied"] is True
    assert data["modelTerms"] == ["gaussian", "lowEnergyTail", "constant", "linear"]
    assert data["degreesOfFreedom"] == expected["degreesOfFreedom"]
    assert data["roi"]["count"] == len(expected["roiIndices"])
    assert data["roi"]["channelMin"] == expected["roiChannelMin"]
    assert data["roi"]["channelMax"] == expected["roiChannelMax"]
    _assert_close(data["roi"]["energyMinKeV"], expected["roiEnergyMin"])
    _assert_close(data["roi"]["energyMaxKeV"], expected["roiEnergyMax"])
    for key, index in {
        "amplitude": 0,
        "tailAmplitude": 1,
        "background": 2,
        "linearSlope": 3,
    }.items():
        _assert_close(data["coefficients"][key], expected["beta"][index])
    _assert_close(data["reducedChiSquare"], expected["reducedChiSquare"])
    assert len(data["covariance"]) == 4
    for row_actual, row_expected in zip(data["covariance"], expected["covariance"], strict=True):
        assert len(row_actual) == 4
        for actual, expected_value in zip(row_actual, row_expected, strict=True):
            _assert_close(actual, expected_value)
    for actual, expected_value in zip(data["fittedRates"], expected["fittedRates"], strict=True):
        _assert_close(actual, expected_value)
    for actual, expected_value in zip(data["residuals"], expected["residuals"], strict=True):
        _assert_close(actual, expected_value)


def test_fit_endpoint_uses_tail_aware_live_rate_weighted_model(
    api_server: tuple[str, subprocess.Popen[str]],
) -> None:
    """Verify /fit applies calibration, live-rate normalization, tail WLS, flags, and covariance."""
    base_url, _process = api_server
    payload = _make_spectrum("Na22")
    response = requests.post(f"{base_url}/fit", json=payload, timeout=5)
    assert response.status_code == 200, response.text
    data = response.json()
    expected = _expected_fit(payload)

    assert data["detectorId"] == "GS-ORION-17"
    _assert_fit_matches(data, expected)
    info = data["normalization"]
    _assert_close(info["liveTimeSec"], payload["liveTimeSec"])
    _assert_close(info["realTimeSec"], payload["realTimeSec"])
    _assert_close(info["deadTimeCorrection"], payload["realTimeSec"] / payload["liveTimeSec"])
    _assert_close(
        info["backgroundScale"],
        payload["liveTimeSec"] / payload["background"]["liveTimeSec"],
    )
    assert info["backgroundSubtracted"] is True
    assert set(data["qualityFlags"]) >= {
        "tail-model-applied",
        "background-subtracted",
        "dead-time-corrected",
    }


def test_bootstrap_endpoint_is_seeded_and_uses_frozen_weight_residual_resampling(
    api_server: tuple[str, subprocess.Popen[str]],
) -> None:
    """Verify /bootstrap matches the documented frozen-weight residual interval."""
    base_url, _process = api_server
    payload = _make_spectrum("Na22", amplitude=3.15, tail=1.05, slope=0.004)
    seed = 24681357
    iterations = 88
    request = {**payload, "seed": seed, "iterations": iterations}
    first = requests.post(f"{base_url}/bootstrap", json=request, timeout=8)
    second = requests.post(f"{base_url}/bootstrap", json=request, timeout=8)
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    first_json = first.json()
    assert first_json == second.json()

    changed = requests.post(f"{base_url}/bootstrap", json={**request, "seed": seed + 1}, timeout=8)
    assert changed.status_code == 200, changed.text
    assert changed.json()["confidence"] != first_json["confidence"]

    expected = _expected_bootstrap(payload, seed, iterations)
    assert first_json["seed"] == seed
    assert first_json["iterations"] == iterations
    assert first_json["statistic"] == "amplitude"
    _assert_close(first_json["pointEstimate"], expected["pointEstimate"])
    for actual, expected_value in zip(
        first_json["confidence"]["ci68"],
        expected["ci68"],
        strict=True,
    ):
        _assert_close(actual, expected_value)
    for actual, expected_value in zip(
        first_json["confidence"]["ci95"],
        expected["ci95"],
        strict=True,
    ):
        _assert_close(actual, expected_value)


def test_bootstrap_rejects_invalid_iteration_counts(
    api_server: tuple[str, subprocess.Popen[str]],
) -> None:
    """Verify /bootstrap returns HTTP 400 for invalid iteration counts with a valid seed."""
    base_url, _process = api_server
    payload = _make_spectrum("Na22")
    for invalid_iterations in (1, 2.5):
        response = requests.post(
            f"{base_url}/bootstrap",
            json={**payload, "seed": 12345, "iterations": invalid_iterations},
            timeout=5,
        )
        assert response.status_code == 400



def test_diagnostics_endpoint_reports_hat_residual_review_metrics(
    api_server: tuple[str, subprocess.Popen[str]],
) -> None:
    """Verify /diagnostics reports leverage-aware residual metrics and review decision."""
    base_url, _process = api_server
    payload = {
        **_make_spectrum("Na22", amplitude=2.75, tail=0.95, slope=0.002),
        "runId": "OR-17-DIAG",
    }
    response = requests.post(f"{base_url}/diagnostics", json=payload, timeout=8)
    assert response.status_code == 200, response.text
    data = response.json()
    expected = _expected_diagnostics(payload)
    fit_expected = expected["fit"]

    assert data["detectorId"] == "GS-ORION-17"
    assert data["isotope"] == "Na22"
    assert data["runId"] == "OR-17-DIAG"
    assert data["method"] == "roi-hat-residual-diagnostics-r2"
    assert data["normalizationRevision"] == expected["normalizationRevision"]
    assert data["roi"] == {
        "count": len(fit_expected["roiIndices"]),
        "energyMinKeV": fit_expected["roiEnergyMin"],
        "energyMaxKeV": fit_expected["roiEnergyMax"],
        "channelMin": fit_expected["roiChannelMin"],
        "channelMax": fit_expected["roiChannelMax"],
    }
    assert data["fit"]["qualityFlags"] == fit_expected["qualityFlags"]
    assert data["fit"]["degreesOfFreedom"] == fit_expected["degreesOfFreedom"]
    _assert_close(data["fit"]["reducedChiSquare"], fit_expected["reducedChiSquare"])
    for key, value in expected["integrals"].items():
        _assert_close(data["integrals"][key], value)
    for key, value in expected["residualDiagnostics"].items():
        _assert_close(data["residualDiagnostics"][key], value)
    assert data["decision"] == expected["decision"]
    assert data["qualityFlags"] == expected["qualityFlags"]


def test_isotope_screen_ranks_candidates_by_aicc(
    api_server: tuple[str, subprocess.Popen[str]],
) -> None:
    """Verify /isotope-screen fits candidate ROIs independently and sorts by AICc."""
    base_url, _process = api_server
    request = {
        "spectrum": _make_screen_spectrum(),
        "candidateIsotopes": ["Na22", "Cs137"],
        "maxResults": 2,
    }
    response = requests.post(f"{base_url}/isotope-screen", json=request, timeout=8)
    assert response.status_code == 200, response.text
    data = response.json()
    expected = _expected_screen(request)

    assert data["detectorId"] == "GS-ORION-17"
    assert data["method"] == "candidate-isotope-wls-aicc-screen-r1"
    assert data["candidateCount"] == 2
    assert data["sortedBy"] == "aicc"
    assert [row["isotope"] for row in data["candidates"]] == [row["isotope"] for row in expected]
    assert data["candidates"][0]["isotope"] == "Cs137"
    for actual, expected_row in zip(data["candidates"], expected, strict=True):
        assert actual["rank"] == expected_row["rank"]
        assert actual["isotope"] == expected_row["isotope"]
        _assert_close(actual["aicc"], expected_row["aicc"])
        _assert_close(actual["deltaAicc"], expected_row["deltaAicc"])
        _assert_close(actual["amplitude"], expected_row["amplitude"])
        _assert_close(actual["reducedChiSquare"], expected_row["reducedChiSquare"])
        assert actual["qualityFlags"] == expected_row["qualityFlags"]
        assert actual["roi"]["count"] == expected_row["roi"]["count"]
        assert actual["roi"]["channelMin"] == expected_row["roi"]["channelMin"]
        assert actual["roi"]["channelMax"] == expected_row["roi"]["channelMax"]
        _assert_close(actual["roi"]["energyMinKeV"], expected_row["roi"]["energyMinKeV"])
        _assert_close(actual["roi"]["energyMaxKeV"], expected_row["roi"]["energyMaxKeV"])


def test_batch_fit_orders_compacts_and_keeps_runs_independent(
    api_server: tuple[str, subprocess.Popen[str]],
) -> None:
    """Verify /batch-fit sorts, compacts output, and isolates runs."""
    base_url, _process = api_server
    run_b = {**_make_spectrum("Na22", amplitude=2.9, tail=0.9), "runId": "OR-17-B"}
    run_a = {
        **_make_spectrum(
            "Cs137",
            live=91.0,
            real=91.0,
            with_background=False,
            amplitude=4.2,
            tail=0.48,
            baseline=0.22,
            slope=-0.003,
        ),
        "runId": "OR-17-A",
    }
    response = requests.post(
        f"{base_url}/batch-fit",
        json={"spectra": [run_b, run_a], "includeResiduals": False},
        timeout=8,
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["detectorId"] == "GS-ORION-17"
    assert data["runCount"] == 2
    assert data["sortedBy"] == "runId"
    assert [entry["runId"] for entry in data["results"]] == ["OR-17-A", "OR-17-B"]

    expected_by_run = {"OR-17-A": _expected_fit(run_a), "OR-17-B": _expected_fit(run_b)}
    compact_keys = {
        "runId",
        "roi",
        "coefficients",
        "normalization",
        "reducedChiSquare",
        "qualityFlags",
    }
    for entry in data["results"]:
        assert set(entry) == compact_keys
        expected = expected_by_run[entry["runId"]]
        expected_roi = {
            "count": len(expected["roiIndices"]),
            "energyMinKeV": expected["roiEnergyMin"],
            "energyMaxKeV": expected["roiEnergyMax"],
            "channelMin": expected["roiChannelMin"],
            "channelMax": expected["roiChannelMax"],
        }
        assert entry["roi"]["count"] == expected_roi["count"]
        assert entry["roi"]["channelMin"] == expected_roi["channelMin"]
        assert entry["roi"]["channelMax"] == expected_roi["channelMax"]
        _assert_close(entry["roi"]["energyMinKeV"], expected_roi["energyMinKeV"])
        _assert_close(entry["roi"]["energyMaxKeV"], expected_roi["energyMaxKeV"])
        for key, index in {
            "amplitude": 0,
            "tailAmplitude": 1,
            "background": 2,
            "linearSlope": 3,
        }.items():
            _assert_close(entry["coefficients"][key], expected["beta"][index])
        _assert_close(entry["reducedChiSquare"], expected["reducedChiSquare"])
        assert entry["qualityFlags"] == expected["qualityFlags"]
        assert entry["normalization"] == expected["normalization"]


def test_invalid_timing_background_and_bootstrap_inputs_are_rejected(
    api_server: tuple[str, subprocess.Popen[str]],
) -> None:
    """Verify bad timing, background, bootstrap, and isotope-screen inputs return HTTP 400."""
    base_url, _process = api_server
    payload = _make_spectrum("Na22")
    bad_timing = {**payload, "realTimeSec": payload["liveTimeSec"] - 0.1}
    timing_response = requests.post(f"{base_url}/fit", json=bad_timing, timeout=5)
    assert timing_response.status_code == 400

    bad_background = json.loads(json.dumps(payload))
    bad_background["background"]["counts"] = bad_background["background"]["counts"][:-1]
    background_response = requests.post(f"{base_url}/fit", json=bad_background, timeout=5)
    assert background_response.status_code == 400

    bad_bootstrap_seed = {**payload, "seed": 1.25, "iterations": 10}
    bootstrap_seed_response = requests.post(
        f"{base_url}/bootstrap",
        json=bad_bootstrap_seed,
        timeout=5,
    )
    assert bootstrap_seed_response.status_code == 400

    bad_screen = {"spectrum": _make_screen_spectrum(), "candidateIsotopes": ["Na22", "Xe999"]}
    screen_response = requests.post(f"{base_url}/isotope-screen", json=bad_screen, timeout=5)
    assert screen_response.status_code == 400


def test_fit_and_batch_requests_do_not_leak_calibration_file_descriptors(
    api_server: tuple[str, subprocess.Popen[str]],
) -> None:
    """Verify repeated /fit and /batch-fit requests keep the Node descriptor count stable."""
    base_url, process = api_server
    fit_payload = _make_spectrum("Na22")
    batch_payload = {
        "spectra": [
            {**_make_spectrum("Na22", amplitude=3.1), "runId": "OR-17-C"},
            {**_make_spectrum("Cs137", with_background=False), "runId": "OR-17-D"},
        ]
    }
    headers = {"Connection": "close"}
    warm_fit = requests.post(f"{base_url}/fit", json=fit_payload, headers=headers, timeout=5)
    assert warm_fit.status_code == 200, warm_fit.text
    warm_batch = requests.post(
        f"{base_url}/batch-fit",
        json=batch_payload,
        headers=headers,
        timeout=8,
    )
    assert warm_batch.status_code == 200, warm_batch.text
    warm_diagnostics = requests.post(
        f"{base_url}/diagnostics",
        json={**fit_payload, "runId": "OR-17-FD"},
        headers=headers,
        timeout=8,
    )
    assert warm_diagnostics.status_code == 200, warm_diagnostics.text
    time.sleep(0.2)
    fd_dir = Path(f"/proc/{process.pid}/fd")
    baseline = len(list(fd_dir.iterdir()))
    for _ in range(28):
        fit_response = requests.post(
            f"{base_url}/fit",
            json=fit_payload,
            headers=headers,
            timeout=5,
        )
        assert fit_response.status_code == 200, fit_response.text
        batch_response = requests.post(
            f"{base_url}/batch-fit",
            json=batch_payload,
            headers=headers,
            timeout=8,
        )
        assert batch_response.status_code == 200, batch_response.text
        diagnostics_response = requests.post(
            f"{base_url}/diagnostics",
            json={**fit_payload, "runId": "OR-17-FD"},
            headers=headers,
            timeout=8,
        )
        assert diagnostics_response.status_code == 200, diagnostics_response.text
    time.sleep(0.2)
    after = len(list(fd_dir.iterdir()))
    assert after <= baseline + 2, f"fd count grew from {baseline} to {after}"


def test_compliance_matrix_covers_expanded_audited_requirements() -> None:
    """Verify the compliance matrix maps each scientific and operational requirement to evidence."""
    assert MATRIX_PATH.exists(), "/app/output/compliance_matrix.json was not written"
    matrix = json.loads(MATRIX_PATH.read_text())
    assert isinstance(matrix.get("task"), str) and matrix["task"].strip()
    assert set(matrix.get("auditCaptures", [])) >= {
        "/app/audit/strace-gammaspec.log",
        "/app/audit/lsof-gammaspec.txt",
    }
    entries = matrix.get("entries")
    assert isinstance(entries, list) and len(entries) >= 8
    by_id = {entry.get("requirementId"): entry for entry in entries if isinstance(entry, dict)}
    required_ids = {
        "GS-CAL-0328",
        "GS-NRM-0417",
        "GS-TAIL-0633",
        "GS-WLS-0182",
        "GS-BS-0441",
        "GS-BAT-0726",
        "GS-QC-0864",
        "GS-DIAG-0911",
        "GS-SCR-1034",
        "GS-MTX-0550",
    }
    assert set(by_id) >= required_ids
    for requirement_id in required_ids:
        entry = by_id[requirement_id]
        assert "/app/docs/gammaspec_methods.md" in entry["source"]
        assert isinstance(entry["fixSummary"], str) and len(entry["fixSummary"].split()) >= 5
        assert isinstance(entry["evidence"], list) and entry["evidence"]
        assert all(isinstance(item, str) and item.startswith("/app/") for item in entry["evidence"])
        assert isinstance(entry["verifiedBy"], list) and entry["verifiedBy"]
        assert all(
            isinstance(item, str) and item.startswith("/app/") for item in entry["verifiedBy"]
        )
    assert any("/app/src/fit.ts" in item for item in by_id["GS-WLS-0182"]["evidence"])
    assert any("/app/src/normalization.ts" in item for item in by_id["GS-NRM-0417"]["evidence"])
    assert any("/app/src/bootstrap.ts" in item for item in by_id["GS-BS-0441"]["evidence"])
    assert any("/app/src/batch.ts" in item for item in by_id["GS-BAT-0726"]["evidence"])
    assert any("/app/src/diagnostics.ts" in item for item in by_id["GS-DIAG-0911"]["evidence"])
    assert any("/app/src/screening.ts" in item for item in by_id["GS-SCR-1034"]["evidence"])
    assert any("/app/src/calibration.ts" in item for item in by_id["GS-CAL-0328"]["evidence"])
