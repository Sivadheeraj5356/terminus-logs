import hashlib
import json
import os
import subprocess

REPORT_PATH = "/app/output/report.json"
SPECTRUM_PATH = "/app/data/raman_spectrum.json"
SPECTRUM_SHA256 = "323200124fbbb2f3f193b7a2a4fb61fd497475de05e6adcaa3b920a41515c4b2"

H = 6.62607015e-34
C = 2.99792458e8
KB = 1.380649e-23
HC_OVER_K = 0.014387773
LASER_NU = 15798.0
SHIFT_CAL = 520.0


def load_spectrum():
    with open(SPECTRUM_PATH) as f:
        return json.load(f)


def load_report():
    with open(REPORT_PATH) as f:
        return json.load(f)


def exp_series(x):
    if x < -700:
        return 0.0
    if x > 700:
        return 1e300
    result = 1.0
    term = 1.0
    for i in range(1, 61):
        term *= x / i
        result += term
    return result


def nat_log(x):
    if x <= 0:
        return 0.0
    y = (x - 1) / (x + 1)
    y2 = y * y
    result = 0.0
    term = y
    for i in range(1, 101, 2):
        result += term / i
        term *= y2
    return 2.0 * result


def detect_peak(points, center_guess, half_window, min_height):
    window = [p for p in points if center_guess - half_window <= p["wavenumber"] <= center_guess + half_window]
    if not window:
        return None
    max_p = max(window, key=lambda p: p["intensity"])
    if max_p["intensity"] < min_height:
        return None
    return max_p


def compute_ref_ratio(laser_nu, shift, exponent):
    nu_plus = laser_nu + shift
    nu_minus = laser_nu - shift
    if nu_plus <= 0 or nu_minus <= 0:
        return 0.0
    return (nu_minus / nu_plus) ** exponent


def compute_ref_temperature(ratio, laser_nu, shift):
    shift = abs(shift)
    if ratio <= 0:
        return 0.0
    nu_plus = laser_nu + shift
    nu_minus = laser_nu - shift
    if nu_plus <= 0 or nu_minus <= 0:
        return 0.0
    freq_factor = (nu_minus / nu_plus) ** 4
    correction = ratio * (1.0 / freq_factor) if freq_factor > 0 else 0.0
    if correction <= 0:
        return 0.0
    ln_corr = nat_log(correction)
    if ln_corr <= 0:
        return 0.0
    return HC_OVER_K * shift / ln_corr


def compute_ref_metrics():
    spec = load_spectrum()
    points = spec["points"]

    stokes_guess = LASER_NU - SHIFT_CAL
    anti_stokes_guess = LASER_NU + SHIFT_CAL

    stokes_peak = detect_peak(points, stokes_guess, 15.0, 10.0)
    anti_stokes_peak = detect_peak(points, anti_stokes_guess, 15.0, 10.0)

    if stokes_peak is None or anti_stokes_peak is None:
        return None

    shift = (stokes_peak["wavenumber"] - anti_stokes_peak["wavenumber"]) / 2.0
    ratio = stokes_peak["intensity"] / anti_stokes_peak["intensity"]

    abs_shift = abs(shift)
    nu_plus = LASER_NU + abs_shift
    nu_minus = LASER_NU - abs_shift
    freq_factor = (nu_minus / nu_plus) ** 4
    expected_ratio = freq_factor * exp_series(HC_OVER_K * abs_shift / 300.0)
    temp = HC_OVER_K * abs_shift / nat_log(ratio / freq_factor)

    return {
        "stokes_peak_center": stokes_peak["wavenumber"],
        "anti_stokes_peak_center": anti_stokes_peak["wavenumber"],
        "peak_shift": shift,
        "ratio": ratio,
        "temperature": temp,
        "expected_ratio": expected_ratio,
    }


def test_report_exists():
    assert os.path.exists(REPORT_PATH), f"Report not found at {REPORT_PATH}"


def test_sample_fields():
    report = load_report()
    assert report["sample"]["sample_id"] == "raman_calib_2025_001"
    assert report["sample"]["method"] == "stokes_anti_stokes_thermometry"


def test_parameters():
    report = load_report()
    p = report["parameters"]
    assert p["bose_model"] == "exact", f"bose_model {p['bose_model']} != exact"
    assert abs(p["temperature_offset"]) < 1e-6, f"temperature_offset {p['temperature_offset']} != 0"
    assert abs(p["frequency_exponent"] - 4.0) < 1e-6, f"exponent {p['frequency_exponent']} != 4"
    assert abs(p["laser_wavenumber"] - 15798.0) < 1.0


def test_raman_shift_derived():
    report = load_report()
    ref = compute_ref_metrics()
    reported_shift = report["parameters"]["raman_shift_cm"]
    expected_shift = ref["peak_shift"]
    assert abs(reported_shift - expected_shift) < 1.0, \
        f"raman_shift_cm {reported_shift} != detected shift {expected_shift}"


def test_peak_positions():
    report = load_report()
    ref = compute_ref_metrics()
    assert abs(report["summary"]["stokes_peak_center"] - ref["stokes_peak_center"]) < 1.0
    assert abs(report["summary"]["anti_stokes_peak_center"] - ref["anti_stokes_peak_center"]) < 1.0


def test_peak_shift():
    report = load_report()
    ref = compute_ref_metrics()
    assert abs(report["summary"]["peak_shift"] - ref["peak_shift"]) < 1.0, \
        f"peak_shift {report['summary']['peak_shift']} != {ref['peak_shift']}"


def test_stokes_anti_stokes_ratio():
    report = load_report()
    ref = compute_ref_metrics()
    ratio = report["summary"]["stokes_anti_stokes_ratio"]
    expected_ratio = ref["ratio"]
    tol = 0.05 * expected_ratio
    assert abs(ratio - expected_ratio) < tol, \
        f"ratio {ratio} != expected {expected_ratio}"


def test_temperature_estimate():
    report = load_report()
    ref = compute_ref_metrics()
    temp = report["summary"]["temperature_estimate"]
    expected_temp = ref["temperature"]
    assert abs(temp - expected_temp) < 2.0, \
        f"temperature {temp} != expected {expected_temp}"


def test_temperature_estimate_positive():
    report = load_report()
    temp = report["summary"]["temperature_estimate"]
    assert 250 < temp < 350, f"Temperature {temp} out of physical range"


def test_parameter_raman_shift_matches_summary_shift():
    report = load_report()
    param_shift = report["parameters"]["raman_shift_cm"]
    summary_shift = report["summary"]["peak_shift"]
    assert abs(param_shift - summary_shift) < 0.1, \
        "parameter raman_shift_cm does not match summary peak_shift"


def test_deterministic_output():
    subprocess.run(["/app/bin/raman-temp"], capture_output=True)
    with open(REPORT_PATH) as f:
        first = json.load(f)
    subprocess.run(["/app/bin/raman-temp"], capture_output=True)
    with open(REPORT_PATH) as f:
        second = json.load(f)
    assert first == second, "Output not deterministic"


def test_binary_exit_code():
    result = subprocess.run(["/app/bin/raman-temp"], capture_output=True)
    assert result.returncode == 0, f"Binary exited with code {result.returncode}"


def test_spectrum_not_modified():
    with open(SPECTRUM_PATH, "rb") as f:
        data = f.read()
    sha = hashlib.sha256(data).hexdigest()
    assert sha == SPECTRUM_SHA256, f"Spectrum SHA256 {sha} does not match expected"
