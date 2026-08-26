import json
import math
import os
import subprocess


TOL = 1e-4
OUTPUT_PATH = "/app/output/fwi_report.json"
CONFIG_PATH = "/app/config/settings.json"
DATA_DIR = "/app/data/fwi"


def r6(v):
    if math.isnan(v) or math.isinf(v):
        return 0.0
    sign = 1 if v >= 0 else -1
    return sign * math.floor(abs(v) * 1000000.0 + 0.5) / 1000000.0


def load_report():
    with open(OUTPUT_PATH) as f:
        return json.load(f)


def load_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)


def load_velocity():
    with open("/var/lib/fwi-truth/true_velocity.json") as f:
        return json.load(f)


def load_sources():
    with open(os.path.join(DATA_DIR, "sources.json")) as f:
        return json.load(f)


def load_receivers():
    with open(os.path.join(DATA_DIR, "receivers.json")) as f:
        return json.load(f)


def load_observed():
    with open(os.path.join(DATA_DIR, "observed_data.json")) as f:
        return json.load(f)


def ricker_wavelet(t, f_mhz, delay):
    tau = t - delay
    arg = math.pi * f_mhz * tau
    arg2 = arg * arg
    return (1.0 - 2.0 * arg2) * math.exp(-arg2)


def compute_travel_time(sx, sz, rx, rz, dx, avg_vel):
    dist = math.sqrt((sx - rx) ** 2 + (sz - rz) ** 2) * dx
    return dist / avg_vel * 1000.0


def test_binary_compiles():
    assert os.path.exists("/app/bin/fwi_ultrasound")


def test_output_exists():
    assert os.path.exists(OUTPUT_PATH)


def test_exit_nonzero_no_args():
    result = subprocess.run(["/app/bin/fwi_ultrasound"], capture_output=True, timeout=10)
    assert result.returncode != 0


def test_deterministic():
    r1 = subprocess.run(
        ["/app/bin/fwi_ultrasound", "--config", CONFIG_PATH,
         "--data-dir", DATA_DIR, "--output", "/tmp/det1.json"],
        capture_output=True, timeout=60)
    r2 = subprocess.run(
        ["/app/bin/fwi_ultrasound", "--config", CONFIG_PATH,
         "--data-dir", DATA_DIR, "--output", "/tmp/det2.json"],
        capture_output=True, timeout=60)
    assert r1.returncode == 0
    assert r2.returncode == 0
    with open("/tmp/det1.json") as f:
        o1 = f.read()
    with open("/tmp/det2.json") as f:
        o2 = f.read()
    assert o1 == o2


def test_all_sections_present():
    report = load_report()
    for key in ["forward_modeling", "attenuation_model", "gradient_computation",
                "velocity_reconstruction", "uncertainty_map", "inversion_summary"]:
        assert key in report, f"Missing: {key}"


def test_forward_modeling_source_count():
    report = load_report()
    sources = load_sources()
    assert len(report["forward_modeling"]) == len(sources["sources"])


def test_forward_modeling_sorted():
    report = load_report()
    ids = [f["source_id"] for f in report["forward_modeling"]]
    assert ids == sorted(ids)


def test_attenuation_model_count():
    report = load_report()
    config = load_config()
    assert len(report["attenuation_model"]) == len(config["source_frequency_mhz"])


def test_attenuation_model_sorted():
    report = load_report()
    freqs = [a["frequency_mhz"] for a in report["attenuation_model"]]
    assert freqs == sorted(freqs)


def test_gradient_computation_count():
    report = load_report()
    config = load_config()
    assert len(report["gradient_computation"]) == config["num_inversion_iterations"]


def test_velocity_reconstruction_dimensions():
    report = load_report()
    config = load_config()
    vel = report["velocity_reconstruction"]["reconstructed_velocity"]
    assert len(vel) == config["grid_nz"]
    for row in vel:
        assert len(row) == config["grid_nx"]


def test_uncertainty_map_dimensions():
    report = load_report()
    config = load_config()
    h = report["uncertainty_map"]["diagonal_hessian"]
    assert len(h) == config["grid_nz"]
    for row in h:
        assert len(row) == config["grid_nx"]
    c = report["uncertainty_map"]["confidence_map"]
    assert len(c) == config["grid_nz"]
    for row in c:
        assert len(row) == config["grid_nx"]


def test_ricker_wavelet_independently():
    report = load_report()
    config = load_config()
    sources = load_sources()
    dt = config["dt_us"]
    nt = config["num_timesteps"]

    for i, src in enumerate(sources["sources"]):
        freq = src["peak_frequency_mhz"]
        delay = src["delay_us"]
        actual_wavelet = report["forward_modeling"][i]["ricker_wavelet"]

        assert len(actual_wavelet) == nt, (
            f"{src['source_id']}: wavelet length {len(actual_wavelet)} != {nt}"
        )

        for t in range(nt):
            time_us = t * dt
            expected = r6(ricker_wavelet(time_us, freq, delay))
            assert abs(actual_wavelet[t] - expected) < TOL, (
                f"{src['source_id']} t={t}: wavelet {actual_wavelet[t]} != {expected}"
            )


def test_ricker_max_amplitude_independently():
    report = load_report()
    config = load_config()
    sources = load_sources()
    dt = config["dt_us"]
    nt = config["num_timesteps"]

    for i, src in enumerate(sources["sources"]):
        freq = src["peak_frequency_mhz"]
        delay = src["delay_us"]
        expected_max = max(
            ricker_wavelet(t * dt, freq, delay) for t in range(nt)
        )
        actual_max = report["forward_modeling"][i]["max_amplitude"]
        assert abs(actual_max - r6(expected_max)) < TOL, (
            f"{src['source_id']}: max_amp {actual_max} != {r6(expected_max)}"
        )


def test_travel_times_independently():
    report = load_report()
    config = load_config()
    sources = load_sources()
    receivers = load_receivers()

    dx = config["dx_mm"]
    avg_vel = config["initial_velocity_mps"]

    for i, src in enumerate(sources["sources"]):
        actual_tt = report["forward_modeling"][i]["travel_times_us"]
        assert len(actual_tt) == len(receivers["receivers"])

        for j, rcv in enumerate(receivers["receivers"]):
            expected_tt = r6(compute_travel_time(
                src["position_ix"], src["position_iz"],
                rcv["position_ix"], rcv["position_iz"],
                dx, avg_vel
            ))
            assert abs(actual_tt[j] - expected_tt) < TOL, (
                f"{src['source_id']}->{rcv['receiver_id']}: "
                f"tt {actual_tt[j]} != {expected_tt}"
            )


def test_attenuation_power_law_independently():
    report = load_report()
    config = load_config()

    alpha0 = config["attenuation_alpha0_np_per_mhz_cm"]
    n = config["attenuation_power_n"]
    freqs = sorted(config["source_frequency_mhz"])

    for i, f in enumerate(freqs):
        expected_coeff = r6(alpha0 * f ** n)
        actual = report["attenuation_model"][i]
        assert abs(actual["frequency_mhz"] - f) < TOL
        assert abs(actual["attenuation_coefficient"] - expected_coeff) < TOL, (
            f"freq {f}: coeff {actual['attenuation_coefficient']} != {expected_coeff}"
        )


def test_attenuation_kramers_kronig_independently():
    report = load_report()
    config = load_config()

    alpha0 = config["attenuation_alpha0_np_per_mhz_cm"]
    n = config["attenuation_power_n"]
    freqs = sorted(config["source_frequency_mhz"])
    f_ref = freqs[0]

    for i, f in enumerate(freqs):
        expected_phase = r6(
            (alpha0 / math.pi) * f ** (n - 1.0) * math.log(f / f_ref + 1e-10)
        )
        actual = report["attenuation_model"][i]["phase_velocity_correction"]
        assert abs(actual - expected_phase) < TOL, (
            f"freq {f}: phase_corr {actual} != {expected_phase}"
        )


def test_attenuation_increases_with_frequency():
    report = load_report()
    coeffs = [a["attenuation_coefficient"] for a in report["attenuation_model"]]
    for i in range(len(coeffs) - 1):
        assert coeffs[i] <= coeffs[i + 1] + TOL, (
            f"Attenuation not monotonically increasing: {coeffs[i]} > {coeffs[i+1]}"
        )


def test_gradient_step_length_decay():
    report = load_report()
    config = load_config()
    step_init = config["step_length_initial"]
    step_red = config["step_length_reduction"]

    for ir in report["gradient_computation"]:
        it = ir["iteration"]
        expected_step = r6(step_init * step_red ** it)
        assert abs(ir["step_length"] - expected_step) < TOL, (
            f"Iter {it}: step {ir['step_length']} != {expected_step}"
        )


def test_gradient_norms_positive():
    report = load_report()
    for ir in report["gradient_computation"]:
        assert ir["gradient_norm"] >= 0
        assert ir["max_gradient"] >= 0
        assert ir["misfit_value"] >= 0


def test_velocity_reconstruction_statistics():
    report = load_report()
    config = load_config()
    vel = report["velocity_reconstruction"]
    nx = config["grid_nx"]
    nz = config["grid_nz"]

    all_vals = [vel["reconstructed_velocity"][iz][ix] for iz in range(nz) for ix in range(nx)]
    expected_mean = r6(sum(all_vals) / len(all_vals))
    expected_min = r6(min(all_vals))
    expected_max = r6(max(all_vals))

    assert abs(vel["mean_velocity_mps"] - expected_mean) < TOL, (
        f"Mean vel: {vel['mean_velocity_mps']} != {expected_mean}"
    )
    assert abs(vel["velocity_range"][0] - expected_min) < TOL
    assert abs(vel["velocity_range"][1] - expected_max) < TOL


def test_velocity_rmse_independently():
    """Verifier independently computes RMSE between reconstructed and true velocity."""
    report = load_report()
    config = load_config()
    vel_data = load_velocity()
    nx = config["grid_nx"]
    nz = config["grid_nz"]

    recon = report["velocity_reconstruction"]["reconstructed_velocity"]
    true_vel = vel_data["velocity_mps"]

    sse = 0.0
    for iz in range(nz):
        for ix in range(nx):
            diff = recon[iz][ix] - true_vel[iz][ix]
            sse += diff * diff
    rmse = r6(math.sqrt(sse / (nx * nz)))
    # RMSE should be reasonable (agent can't cheat by copying truth)
    assert rmse > 0, "RMSE is 0 — reconstructed velocity may be copied from truth"
    assert rmse < 500, f"RMSE {rmse} too large — reconstruction did not converge"


def test_confidence_map_formula():
    report = load_report()
    config = load_config()
    nx = config["grid_nx"]
    nz = config["grid_nz"]

    hessian = report["uncertainty_map"]["diagonal_hessian"]
    confidence = report["uncertainty_map"]["confidence_map"]

    for iz in range(nz):
        for ix in range(nx):
            h = hessian[iz][ix]
            expected_conf = r6(1.0 / (1.0 + h))
            actual_conf = confidence[iz][ix]
            assert abs(actual_conf - expected_conf) < TOL, (
                f"({ix},{iz}): conf {actual_conf} != 1/(1+{h})={expected_conf}"
            )


def test_confidence_map_range():
    report = load_report()
    config = load_config()
    nx = config["grid_nx"]
    nz = config["grid_nz"]

    confidence = report["uncertainty_map"]["confidence_map"]
    for iz in range(nz):
        for ix in range(nx):
            assert 0.0 <= confidence[iz][ix] <= 1.0 + TOL, (
                f"({ix},{iz}): confidence {confidence[iz][ix]} out of [0,1]"
            )


def test_uncertainty_statistics():
    report = load_report()
    config = load_config()
    nx = config["grid_nx"]
    nz = config["grid_nz"]

    hessian = report["uncertainty_map"]["diagonal_hessian"]
    all_h = [hessian[iz][ix] for iz in range(nz) for ix in range(nx)]
    expected_mean = r6(sum(all_h) / len(all_h))
    expected_max = r6(max(all_h))

    assert abs(report["uncertainty_map"]["mean_uncertainty"] - expected_mean) < TOL
    assert abs(report["uncertainty_map"]["max_uncertainty"] - expected_max) < TOL


def test_hessian_non_negative():
    report = load_report()
    config = load_config()
    nx = config["grid_nx"]
    nz = config["grid_nz"]

    hessian = report["uncertainty_map"]["diagonal_hessian"]
    for iz in range(nz):
        for ix in range(nx):
            assert hessian[iz][ix] >= -TOL, (
                f"({ix},{iz}): negative hessian {hessian[iz][ix]}"
            )


def test_inversion_summary_forward_solves():
    report = load_report()
    config = load_config()
    nsrc = config["num_sources"]
    niter = config["num_inversion_iterations"]
    expected = nsrc * niter
    assert report["inversion_summary"]["total_forward_solves"] == expected


def test_inversion_summary_adjoint_solves():
    report = load_report()
    config = load_config()
    nsrc = config["num_sources"]
    niter = config["num_inversion_iterations"]
    expected = nsrc * niter
    assert report["inversion_summary"]["total_adjoint_solves"] == expected


def test_inversion_summary_final_misfit():
    report = load_report()
    last_iter = report["gradient_computation"][-1]
    assert abs(report["inversion_summary"]["final_misfit"] - last_iter["misfit_value"]) < TOL


def test_inversion_summary_misfit_reduction():
    report = load_report()
    first_misfit = report["gradient_computation"][0]["misfit_value"]
    final_misfit = report["inversion_summary"]["final_misfit"]
    if first_misfit > 0:
        expected_red = r6((1.0 - final_misfit / first_misfit) * 100.0)
    else:
        expected_red = 0.0
    actual = report["inversion_summary"]["misfit_reduction_percent"]
    assert abs(actual - expected_red) < 0.01, (
        f"Reduction: {actual} != {expected_red}"
    )


def test_inversion_summary_frequencies():
    report = load_report()
    config = load_config()
    expected = sorted(config["source_frequency_mhz"])
    actual = report["inversion_summary"]["frequencies_used"]
    assert len(actual) == len(expected)
    for i in range(len(expected)):
        assert abs(actual[i] - expected[i]) < TOL


def test_no_nan_or_inf():
    report = load_report()

    def check(obj, path="root"):
        if isinstance(obj, float):
            assert not math.isnan(obj), f"NaN at {path}"
            assert not math.isinf(obj), f"Inf at {path}"
        elif isinstance(obj, dict):
            for k, v in obj.items():
                check(v, f"{path}.{k}")
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                check(v, f"{path}[{i}]")

    check(report)


def test_rounding_precision():
    report = load_report()
    for am in report["attenuation_model"]:
        assert abs(am["attenuation_coefficient"] - round(am["attenuation_coefficient"], 6)) < 1e-9
    for ir in report["gradient_computation"]:
        assert abs(ir["misfit_value"] - round(ir["misfit_value"], 6)) < 1e-9


def test_ricker_wavelet_zero_crossing_properties():
    report = load_report()
    config = load_config()
    sources = load_sources()
    dt = config["dt_us"]
    nt = config["num_timesteps"]

    for i, src in enumerate(sources["sources"]):
        freq = src["peak_frequency_mhz"]
        delay = src["delay_us"]
        wavelet = report["forward_modeling"][i]["ricker_wavelet"]

        zero_crossings = 0
        for t in range(1, nt):
            if wavelet[t] * wavelet[t - 1] < 0:
                zero_crossings += 1

        assert zero_crossings >= 1, (
            f"{src['source_id']}: Ricker wavelet should have at least 1 zero crossing, "
            f"got {zero_crossings}"
        )

        peak_idx = wavelet.index(max(wavelet))
        peak_time = peak_idx * dt
        assert abs(peak_time - delay) < 2 * dt + 1.0 / freq, (
            f"{src['source_id']}: peak at t={peak_time} too far from delay={delay}"
        )

        energy = sum(w * w for w in wavelet)
        assert energy > 0, f"{src['source_id']}: wavelet has zero energy"

        for t in range(nt):
            time_us = t * dt
            expected = r6(ricker_wavelet(time_us, freq, delay))
            assert abs(wavelet[t] - expected) < TOL, (
                f"{src['source_id']} t={t}: {wavelet[t]} != {expected}"
            )


def test_travel_time_symmetry_and_positivity():
    report = load_report()
    sources = load_sources()
    receivers = load_receivers()

    {s["source_id"]: (s["position_ix"], s["position_iz"])
                     for s in sources["sources"]}
    {r["receiver_id"]: (r["position_ix"], r["position_iz"])
                     for r in receivers["receivers"]}

    for fm in report["forward_modeling"]:
        for tt in fm["travel_times_us"]:
            assert tt >= 0, (
                f"{fm['source_id']}: negative travel time {tt}"
            )

    for i, fm_a in enumerate(report["forward_modeling"]):
        src_a = sources["sources"][i]
        for j, fm_b in enumerate(report["forward_modeling"]):
            sources["sources"][j]
            for k, rcv in enumerate(receivers["receivers"]):
                if (src_a["position_ix"] == rcv["position_ix"] and
                        src_a["position_iz"] == rcv["position_iz"]):
                    assert fm_a["travel_times_us"][k] < TOL, (
                        f"{src_a['source_id']}: zero-distance travel time should be ~0"
                    )


def test_travel_time_triangle_inequality():
    report = load_report()
    config = load_config()
    sources = load_sources()
    receivers = load_receivers()
    dx = config["dx_mm"]

    for i, fm in enumerate(report["forward_modeling"]):
        src = sources["sources"][i]
        for j in range(len(receivers["receivers"])):
            rcv = receivers["receivers"][j]
            dist = math.sqrt(
                (src["position_ix"] - rcv["position_ix"]) ** 2 +
                (src["position_iz"] - rcv["position_iz"]) ** 2
            ) * dx
            max_vel = 1600.0
            min_vel = 1400.0
            min_tt = dist / max_vel * 1000.0
            dist / min_vel * 1000.0
            actual_tt = fm["travel_times_us"][j]
            assert actual_tt >= min_tt - TOL, (
                f"{src['source_id']}->{rcv['receiver_id']}: "
                f"tt={actual_tt} < min possible {min_tt}"
            )


def test_attenuation_physical_consistency():
    report = load_report()
    config = load_config()
    alpha0 = config["attenuation_alpha0_np_per_mhz_cm"]
    n = config["attenuation_power_n"]

    for am in report["attenuation_model"]:
        f = am["frequency_mhz"]
        coeff = am["attenuation_coefficient"]

        assert coeff > 0, f"freq {f}: attenuation should be positive"

        expected = alpha0 * f ** n
        assert abs(coeff - r6(expected)) < TOL, (
            f"freq {f}: coeff {coeff} != alpha0*f^n = {alpha0}*{f}^{n} = {r6(expected)}"
        )

        if n > 1:
            assert am["phase_velocity_correction"] > 0 or f == report["attenuation_model"][0]["frequency_mhz"], (
                f"freq {f}: phase correction should be positive for n>1 at non-reference freq"
            )


def test_full_attenuation_computation_all_frequencies():
    report = load_report()
    config = load_config()
    alpha0 = config["attenuation_alpha0_np_per_mhz_cm"]
    n = config["attenuation_power_n"]
    freqs = sorted(set(config["source_frequency_mhz"]))
    f_ref = freqs[0]

    for i, f in enumerate(freqs):
        expected_coeff = r6(alpha0 * f ** n)
        expected_phase = r6((alpha0 / math.pi) * f ** (n - 1.0) * math.log(f / f_ref + 1e-10))

        actual = report["attenuation_model"][i]
        assert abs(actual["frequency_mhz"] - f) < TOL
        assert abs(actual["attenuation_coefficient"] - expected_coeff) < TOL, (
            f"f={f}: coeff got {actual['attenuation_coefficient']}, "
            f"expected alpha0*f^n = {alpha0}*{f}^{n} = {expected_coeff}"
        )
        assert abs(actual["phase_velocity_correction"] - expected_phase) < TOL, (
            f"f={f}: phase got {actual['phase_velocity_correction']}, "
            f"expected (alpha0/pi)*f^(n-1)*ln(f/f_ref) = {expected_phase}"
        )


def test_gradient_misfit_decreasing_trend():
    report = load_report()
    misfits = [ir["misfit_value"] for ir in report["gradient_computation"]]
    decreasing_count = sum(1 for i in range(1, len(misfits)) if misfits[i] <= misfits[i-1] + TOL)
    assert decreasing_count >= len(misfits) // 2, (
        f"Misfit should generally decrease: {misfits}"
    )


def test_gradient_step_length_all_iterations():
    report = load_report()
    config = load_config()
    step_init = config["step_length_initial"]
    step_red = config["step_length_reduction"]
    niter = config["num_inversion_iterations"]

    for it in range(niter):
        expected = r6(step_init * step_red ** it)
        actual = report["gradient_computation"][it]["step_length"]
        assert abs(actual - expected) < TOL, (
            f"Iter {it}: step = init * red^it = "
            f"{step_init} * {step_red}^{it} = {expected}, got {actual}"
        )

    for i in range(1, niter):
        assert report["gradient_computation"][i]["step_length"] <= report["gradient_computation"][i-1]["step_length"] + TOL, (
            "Step length should be non-increasing"
        )


def test_velocity_grid_all_values_physical():
    report = load_report()
    config = load_config()
    nx = config["grid_nx"]
    nz = config["grid_nz"]

    vel = report["velocity_reconstruction"]["reconstructed_velocity"]
    for iz in range(nz):
        for ix in range(nx):
            v = vel[iz][ix]
            assert 1000.0 <= v <= 2000.0, (
                f"({ix},{iz}): velocity {v} outside physical range [1000, 2000] m/s"
            )


def test_velocity_rmse_computation_independently():
    """Verify reconstructed velocity differs from truth (no cheating) and is reasonable."""
    report = load_report()
    config = load_config()
    vel_data = load_velocity()
    nx = config["grid_nx"]
    nz = config["grid_nz"]

    recon = report["velocity_reconstruction"]["reconstructed_velocity"]
    true_v = vel_data["velocity_mps"]

    sum_sq = 0.0
    count = 0
    max_error = 0.0
    for iz in range(nz):
        for ix in range(nx):
            diff = recon[iz][ix] - true_v[iz][ix]
            sum_sq += diff * diff
            max_error = max(max_error, abs(diff))
            count += 1

    rmse = r6(math.sqrt(sum_sq / count))
    # Reconstruction should not be perfect (agent doesn't have truth)
    assert rmse > 0.1, (
        f"RMSE {rmse} is suspiciously low — agent may have copied truth data"
    )
    assert rmse < 500, (
        f"RMSE {rmse} too high — reconstruction has not converged"
    )


def test_velocity_mean_computation_independently():
    report = load_report()
    config = load_config()
    nx = config["grid_nx"]
    nz = config["grid_nz"]

    vel = report["velocity_reconstruction"]["reconstructed_velocity"]
    all_vals = []
    for iz in range(nz):
        for ix in range(nx):
            all_vals.append(vel[iz][ix])

    expected_mean = r6(sum(all_vals) / len(all_vals))
    expected_min = r6(min(all_vals))
    expected_max = r6(max(all_vals))

    assert abs(report["velocity_reconstruction"]["mean_velocity_mps"] - expected_mean) < TOL, (
        f"Mean: got {report['velocity_reconstruction']['mean_velocity_mps']}, expected {expected_mean}"
    )
    assert abs(report["velocity_reconstruction"]["velocity_range"][0] - expected_min) < TOL, (
        f"Min: got {report['velocity_reconstruction']['velocity_range'][0]}, expected {expected_min}"
    )
    assert abs(report["velocity_reconstruction"]["velocity_range"][1] - expected_max) < TOL, (
        f"Max: got {report['velocity_reconstruction']['velocity_range'][1]}, expected {expected_max}"
    )


def test_confidence_map_all_400_points():
    report = load_report()
    config = load_config()
    nx = config["grid_nx"]
    nz = config["grid_nz"]

    hessian = report["uncertainty_map"]["diagonal_hessian"]
    confidence = report["uncertainty_map"]["confidence_map"]

    total_checked = 0
    for iz in range(nz):
        for ix in range(nx):
            h = hessian[iz][ix]
            expected_conf = r6(1.0 / (1.0 + h))
            actual_conf = confidence[iz][ix]

            assert abs(actual_conf - expected_conf) < TOL, (
                f"({ix},{iz}): confidence = 1/(1+H) = 1/(1+{h}) = {expected_conf}, "
                f"got {actual_conf}"
            )

            assert h >= -TOL, f"({ix},{iz}): negative hessian {h}"
            assert 0.0 - TOL <= actual_conf <= 1.0 + TOL, (
                f"({ix},{iz}): confidence {actual_conf} out of [0,1]"
            )
            total_checked += 1

    assert total_checked == nx * nz, (
        f"Only checked {total_checked}/{nx*nz} points"
    )


def test_uncertainty_mean_max_independently():
    report = load_report()
    config = load_config()
    nx = config["grid_nx"]
    nz = config["grid_nz"]

    hessian = report["uncertainty_map"]["diagonal_hessian"]
    all_h = []
    for iz in range(nz):
        for ix in range(nx):
            all_h.append(hessian[iz][ix])

    expected_mean = r6(sum(all_h) / len(all_h))
    expected_max = r6(max(all_h))

    assert abs(report["uncertainty_map"]["mean_uncertainty"] - expected_mean) < TOL, (
        f"Mean uncertainty: got {report['uncertainty_map']['mean_uncertainty']}, "
        f"expected {expected_mean}"
    )
    assert abs(report["uncertainty_map"]["max_uncertainty"] - expected_max) < TOL, (
        f"Max uncertainty: got {report['uncertainty_map']['max_uncertainty']}, "
        f"expected {expected_max}"
    )


def test_inversion_summary_solve_counts():
    report = load_report()
    config = load_config()
    nsrc = config["num_sources"]
    niter = config["num_inversion_iterations"]

    expected_fwd = nsrc * niter
    expected_adj = nsrc * niter

    assert report["inversion_summary"]["total_forward_solves"] == expected_fwd, (
        f"Forward: {report['inversion_summary']['total_forward_solves']} != "
        f"nsrc*niter = {nsrc}*{niter} = {expected_fwd}"
    )
    assert report["inversion_summary"]["total_adjoint_solves"] == expected_adj, (
        f"Adjoint: {report['inversion_summary']['total_adjoint_solves']} != "
        f"nsrc*niter = {nsrc}*{niter} = {expected_adj}"
    )


def test_inversion_final_misfit_matches_last_iteration():
    report = load_report()
    last_misfit = report["gradient_computation"][-1]["misfit_value"]
    summary_misfit = report["inversion_summary"]["final_misfit"]
    assert abs(summary_misfit - last_misfit) < TOL, (
        f"Final misfit in summary ({summary_misfit}) != last iteration ({last_misfit})"
    )


def test_inversion_frequencies_match_config():
    report = load_report()
    config = load_config()
    expected = sorted(config["source_frequency_mhz"])
    actual = sorted(report["inversion_summary"]["frequencies_used"])
    assert len(actual) == len(expected)
    for i in range(len(expected)):
        assert abs(actual[i] - expected[i]) < TOL, (
            f"Frequency {i}: {actual[i]} != {expected[i]}"
        )


def test_wavelet_length_matches_timesteps():
    report = load_report()
    config = load_config()
    nt = config["num_timesteps"]
    nrcv = config["num_receivers"]

    for fm in report["forward_modeling"]:
        assert len(fm["ricker_wavelet"]) == nt, (
            f"{fm['source_id']}: wavelet length {len(fm['ricker_wavelet'])} != {nt}"
        )
        assert len(fm["travel_times_us"]) == nrcv, (
            f"{fm['source_id']}: travel_times length {len(fm['travel_times_us'])} != {nrcv}"
        )


def test_iteration_numbers_sequential():
    report = load_report()
    for i, ir in enumerate(report["gradient_computation"]):
        assert ir["iteration"] == i, (
            f"Iteration {i}: got iteration number {ir['iteration']}"
        )
