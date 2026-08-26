"""Behavioral verification for the reduced-order kirigami sheet analyzer."""

from __future__ import annotations

import copy
import hashlib
import json
import math
import os
import random
import subprocess
from pathlib import Path

import pytest

APP_ROOT = Path(os.environ.get("KIRIGAMI_APP_ROOT", "/app"))
BINARY = Path(os.environ.get("KIRIGAMI_BINARY", str(APP_ROOT / "bin" / "kirigami-map")))
RUN_UID = int(os.environ.get("KIRIGAMI_RUN_UID", "-1"))

PROTECTED_HASHES = {
    'cases/bench-01.json': '83dc93d27648221ce3e64c5ef7ff032ef93d93bdd1259e687f13bf4852ae5934',
    'cases/bench-02.json': '7092edc2ec4ec9123f652f94a0a2242d931b89d58d03c31533579e9dc8fd4e54',
    'cases/bench-03.json': '8f4734916bcc0ab892dd3cc046a2a3ffdb50bb25d12ed4519d3bb4cf1cc5b082',
    'cases/bench-04.json': '0a0f06c262d43ac7ec9a9dff15bb488ddcccbed8cc6e690d802807bc273914ae',
    'cases/bench-05.json': '8bc7da84dcc24d81931ad386c8a3e8ff26316b851a9ddd46919be9d71b94eb4b',
    'cases/bench-06.json': '98897c1ecd087b7953043c9c54cf932de6c6f183b8fbacdc98ba2433f047d385',
    'cases/bench-07.json': '3dd627a96946301f280c7f0d9cddae5cca29517f251c8edca245345da2214848',
    'cases/bench-08.json': '5100226a954c0292f9da4f0933d45f0cc4bd0c3045db2d565f85a1ebba8c1b3d',
    'cases/bench-09.json': '378360b911d91f92afec534767174c2b83a70f0c9a2b03e24e80075fc7a89549',
    'cases/bench-10.json': '8e73a68eaa7bcce4ed10abc1971b0e75c3754e2efddc1fb3b0aa103755098116',
    'cases/bench-11.json': 'c8476d068886723ef00749c226dbdbf4df435173b45b23dcb2fb75e43866fea3',
    'cases/bench-12.json': '109aac67cdfe6cece6cfe8a408b625a117020f05415ccf8f28c7f868afd1a28f',
    'cases/bench-13.json': 'e64369c60d3b712798b6bf80cb4dd9402e2f0bf72e19a4744407cc66379c3f63',
    'cases/bench-14.json': '1595b4cfe61b7487867bd51f2bf6463a521e217c250df3c3c5dffa53c3a07b00',
    'cases/bench-15.json': '22f755d6511c69aea7da4b555d92d015554ce007b5ef2a44ac4232399eb9f9a1',
    'cases/bench-16.json': '401c1a175ccbc0fbf328ab2510afa5758ac7306d0bf7f7b580b2bf5a535fbc40',
    'cases/bench-17.json': '31590931798fd2e1908d3b6ea376ac09ad9a00dee5550440e1d7166726ecda9d',
    'cases/bench-18.json': 'e1f35d09af1075069ac3ee274a20943a2adf5409a6bb66724f41e86514260162',
    'cases/bench-19.json': '7a03364d3fc64cea0293c50ea6efe3e2c0b0fc36d5c7e54cdd9e7dd06df4fae2',
    'cases/bench-20.json': 'd7aaed1ca5cc086b92dcc0e3f4cd6e1c8e6f5165d966306fc5e69212191bf164',
    'cases/bench-21.json': 'acf24e381c7aa5255a112567dad411cbd0bba61a513356e036cbcc24b62a2ec0',
    'cases/bench-22.json': 'b55f9f72d94fd03e42abd4d914ebfe6f11e905d5d3b1bd13349492d6eb3c0315',
    'docs/analysis-contract.md': '0b31af59ca4160b9adc62631ff323fd110072494e61978f3b7f3cb79e46dc238',
    'docs/rig-note.txt': '07c8f3a741892f320b733bfa7e4a519ffde13cf7d91a14799afb8717e389090a',
}


@pytest.fixture(autouse=True)
def _candidate_writable_tmp(tmp_path: Path) -> None:
    """Allow the unprivileged submitted executable to create and replace test outputs."""
    current = tmp_path
    while current != Path("/tmp"):
        current.chmod(0o777)
        current = current.parent


def _candidate_run(arguments: list[str], *, timeout: int) -> subprocess.CompletedProcess[str]:
    kwargs: dict[str, object] = {}
    if RUN_UID >= 0 and os.geteuid() == 0:
        kwargs.update(user=RUN_UID, group=RUN_UID, extra_groups=[])
    return subprocess.run(
        [str(BINARY), *arguments],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
        **kwargs,
    )


def _trim(poly: list[float]) -> list[float]:
    while len(poly) > 1 and abs(poly[-1]) < 1e-18:
        poly.pop()
    return poly


def _poly_eval(poly: list[float], x: float) -> float:
    value = 0.0
    for coefficient in reversed(poly):
        value = value * x + coefficient
    return value


def _poly_derivative(poly: list[float]) -> list[float]:
    return [index * poly[index] for index in range(1, len(poly))] or [0.0]


def _bisect_polynomial(poly: list[float], left: float, right: float) -> float:
    f_left = _poly_eval(poly, left)
    for _ in range(140):
        middle = (left + right) / 2.0
        f_middle = _poly_eval(poly, middle)
        if abs(f_middle) < 1e-14 or right - left < 1e-13 * (1.0 + abs(middle)):
            return middle
        if f_left * f_middle <= 0.0:
            right = middle
        else:
            left = middle
            f_left = f_middle
    return (left + right) / 2.0


def _real_polynomial_roots(poly: list[float], left: float, right: float) -> list[float]:
    poly = _trim(list(poly))
    degree = len(poly) - 1
    if degree <= 0:
        return []
    if degree == 1:
        root = -poly[0] / poly[1]
        return [min(right, max(left, root))] if left - 1e-10 <= root <= right + 1e-10 else []

    critical = _real_polynomial_roots(_poly_derivative(poly), left, right)
    points = [left, *[x for x in critical if left + 1e-12 < x < right - 1e-12], right]
    roots = [x for x in points if abs(_poly_eval(poly, x)) < 1e-9]
    for a, b in zip(points, points[1:]):
        fa = _poly_eval(poly, a)
        fb = _poly_eval(poly, b)
        if fa * fb < 0.0:
            roots.append(_bisect_polynomial(poly, a, b))
    roots.sort()
    unique: list[float] = []
    for root in roots:
        if not unique or abs(root - unique[-1]) > 1e-7 * (1.0 + abs(root)):
            unique.append(root)
    return unique


def _active_indices(model: dict, theta: float, side: int = 0) -> list[int]:
    active = []
    for index, stop in enumerate(model["stops"]):
        angle = stop["angle"]
        if stop["sense"] == "upper":
            enabled = theta > angle or (abs(theta - angle) < 1e-12 and side > 0)
        else:
            enabled = theta < angle or (abs(theta - angle) < 1e-12 and side < 0)
        if enabled:
            active.append(index)
    return active


def _force(model: dict, theta: float, side: int = 0) -> float:
    value = model["a1"] * theta + model["a3"] * theta**3 + model["a5"] * theta**5
    for index in _active_indices(model, theta, side):
        stop = model["stops"][index]
        value += stop["stiffness"] * (theta - stop["angle"])
    return value


def _drive(model: dict, theta: float) -> float:
    return model["b1"] + model["b3"] * theta**2


def _load_curve(model: dict, theta: float) -> float:
    return _force(model, theta) / _drive(model, theta)


def _tangent(model: dict, theta: float, load: float, side: int = 0) -> float:
    value = (
        model["a1"]
        + 3.0 * model["a3"] * theta**2
        + 5.0 * model["a5"] * theta**4
        - 2.0 * load * model["b3"] * theta
    )
    for index in _active_indices(model, theta, side):
        value += model["stops"][index]["stiffness"]
    return value


def _energy(model: dict, theta: float, load: float) -> float:
    value = (
        model["a1"] * theta**2 / 2.0
        + model["a3"] * theta**4 / 4.0
        + model["a5"] * theta**6 / 6.0
        - load * (model["b1"] * theta + model["b3"] * theta**3 / 3.0)
    )
    for stop in model["stops"]:
        offset = theta - stop["angle"]
        if (stop["sense"] == "upper" and offset > 0.0) or (stop["sense"] == "lower" and offset < 0.0):
            value += stop["stiffness"] * offset**2 / 2.0
    return value


def _stability(model: dict, theta: float, load: float) -> str:
    left = _tangent(model, theta, load, -1)
    right = _tangent(model, theta, load, 1)
    if left > 1e-7 and right > 1e-7:
        return "stable"
    if left < -1e-7 and right < -1e-7:
        return "unstable"
    return "neutral"


def _multiply(left: list[float], right: list[float]) -> list[float]:
    result = [0.0] * (len(left) + len(right) - 1)
    for i, a in enumerate(left):
        for j, b in enumerate(right):
            result[i + j] += a * b
    return result


def _fold_polynomial(model: dict, midpoint: float) -> list[float]:
    force_poly = [0.0, model["a1"], 0.0, model["a3"], 0.0, model["a5"]]
    for stop in model["stops"]:
        active = midpoint > stop["angle"] if stop["sense"] == "upper" else midpoint < stop["angle"]
        if active:
            force_poly[1] += stop["stiffness"]
            force_poly[0] -= stop["stiffness"] * stop["angle"]
    drive_poly = [model["b1"], 0.0, model["b3"]]
    first = _multiply(_poly_derivative(force_poly), drive_poly)
    second = _multiply(force_poly, _poly_derivative(drive_poly))
    size = max(len(first), len(second))
    first += [0.0] * (size - len(first))
    second += [0.0] * (size - len(second))
    return _trim([a - b for a, b in zip(first, second, strict=True)])


def _folds(model: dict) -> list[float]:
    cuts = [model["theta_min"], model["theta_max"], *[stop["angle"] for stop in model["stops"]]]
    cuts = sorted(set(cuts))
    folds: list[float] = []
    for left, right in zip(cuts, cuts[1:]):
        for theta in _real_polynomial_roots(_fold_polynomial(model, (left + right) / 2.0), left, right):
            if theta <= left + 1e-7 or theta >= right - 1e-7:
                continue
            step = min(1e-5 * (1.0 + abs(theta)), 0.1 * min(theta - left, right - theta))
            center = _load_curve(model, theta)
            before = _load_curve(model, theta - step)
            after = _load_curve(model, theta + step)
            if (center > before and center > after) or (center < before and center < after):
                folds.append(theta)
    folds.sort()
    return [x for index, x in enumerate(folds) if index == 0 or abs(x - folds[index - 1]) > 1e-7]


def _partition(model: dict) -> list[float]:
    points = [model["theta_min"], model["theta_max"], *[stop["angle"] for stop in model["stops"]], *_folds(model)]
    points.sort()
    unique: list[float] = []
    for point in points:
        if not unique or abs(point - unique[-1]) > 1e-8:
            unique.append(point)
    return unique


def _equilibria(model: dict, load: float) -> list[float]:
    roots: list[float] = []
    points = _partition(model)
    for left, right in zip(points, points[1:]):
        f_left = _load_curve(model, left) - load
        f_right = _load_curve(model, right) - load
        if load < min(_load_curve(model, left), _load_curve(model, right)) - 1e-9:
            continue
        if load > max(_load_curve(model, left), _load_curve(model, right)) + 1e-9:
            continue
        if abs(f_left) < 1e-9:
            roots.append(left)
        if abs(f_right) < 1e-9:
            roots.append(right)
        if f_left * f_right < 0.0:
            a, b = left, right
            fa = f_left
            for _ in range(120):
                middle = (a + b) / 2.0
                fm = _load_curve(model, middle) - load
                if abs(fm) < 1e-13 or b - a < 1e-12 * (1.0 + abs(middle)):
                    break
                if fa * fm <= 0.0:
                    b = middle
                else:
                    a = middle
                    fa = fm
            roots.append((a + b) / 2.0)
    roots.sort()
    unique: list[float] = []
    for root in roots:
        if not unique or abs(root - unique[-1]) > 1e-6 * (1.0 + abs(root)):
            unique.append(root)
    return unique


def _stable_roots(model: dict, load: float) -> list[float]:
    return [theta for theta in _equilibria(model, load) if _stability(model, theta, load) == "stable"]


def _reference_sweep(model: dict, loads: list[float], initial_theta: float) -> list[dict]:
    initial_candidates = _stable_roots(model, loads[0])
    if not initial_candidates:
        raise ValueError("no initial stable root")
    previous = min(initial_candidates, key=lambda theta: abs(theta - initial_theta))
    if abs(previous - initial_theta) > 1e-5:
        raise ValueError("initial mismatch")
    output = [
        {
            "load": loads[0],
            "theta": previous,
            "energy": _energy(model, previous, loads[0]),
            "transition": "initial",
        }
    ]
    direction = 1 if loads[-1] > loads[0] else -1
    branch_points = [model["theta_min"], *_folds(model), model["theta_max"]]
    for load in loads[1:]:
        bounds = next(
            (pair for pair in zip(branch_points, branch_points[1:]) if pair[0] - 1e-8 <= previous <= pair[1] + 1e-8),
            None,
        )
        stable = _stable_roots(model, load)
        same_branch = [theta for theta in stable if bounds and bounds[0] - 1e-8 <= theta <= bounds[1] + 1e-8]
        if same_branch:
            current = min(same_branch, key=lambda theta: abs(theta - previous))
            transition = "follow"
        else:
            if not stable:
                raise ValueError("no stable root")
            residual = _force(model, previous) - load * _drive(model, previous)
            move = -1 if residual > 1e-9 else 1 if residual < -1e-9 else direction
            side = [theta for theta in stable if (theta - previous) * move > 1e-9]
            current = min(side or stable, key=lambda theta: abs(theta - previous))
            transition = "snap"
        output.append(
            {"load": load, "theta": current, "energy": _energy(model, current, load), "transition": transition}
        )
        previous = current
    return output


def _hidden_model(seed: int) -> dict:
    generator = random.Random(seed)
    model = {
        "a1": generator.uniform(-1.0, 2.2),
        "a3": generator.uniform(-5.0, -1.0),
        "a5": generator.uniform(0.65, 2.1),
        "b1": generator.uniform(0.65, 1.5),
        "b3": generator.uniform(0.0, 0.35),
        "theta_min": -2.25,
        "theta_max": 2.25,
        "stops": [],
    }
    stop_count = seed % 4
    candidate_angles = [-1.55, -0.75, 0.45, 1.35]
    for index in range(stop_count):
        angle = candidate_angles[(seed + 2 * index) % len(candidate_angles)] + generator.uniform(-0.08, 0.08)
        sense = "upper" if (seed + index) % 2 else "lower"
        model["stops"].append(
            {"sense": sense, "angle": angle, "stiffness": generator.uniform(0.7, 7.0)}
        )
    return model


def _load_span(model: dict) -> tuple[float, float]:
    values = [_load_curve(model, model["theta_min"]), _load_curve(model, model["theta_max"])]
    values.extend(_load_curve(model, theta) for theta in _folds(model))
    low = max(min(values[0], values[1]) + 0.03, min(values) - 0.12)
    high = min(max(values[0], values[1]) - 0.03, max(values) + 0.12)
    if low >= high:
        low, high = min(values[0], values[1]) + 0.05, max(values[0], values[1]) - 0.05
    return low, high


def _linspace(start: float, stop: float, count: int) -> list[float]:
    return [start + (stop - start) * index / (count - 1) for index in range(count)]


def _campaign(seed: int, query_count: int = 7, sweep_count: int = 21) -> dict:
    model = _hidden_model(seed)
    low, high = _load_span(model)
    loads = _linspace(low, high, query_count)
    sweep_loads = _linspace(low, high, sweep_count)
    left_stable = _stable_roots(model, sweep_loads[0])
    right_stable = _stable_roots(model, sweep_loads[-1])
    if not left_stable or not right_stable:
        raise AssertionError(f"bad hidden model seed {seed}")
    return {
        "schema": "kirigami-campaign-v1",
        "campaign": f"hidden-{seed}",
        "model": model,
        "equilibrium_loads": loads,
        "sweeps": [
            {"id": "up", "loads": sweep_loads, "initial_theta": min(left_stable)},
            {"id": "down", "loads": list(reversed(sweep_loads)), "initial_theta": max(right_stable)},
        ],
    }


def _run(campaign: dict, tmp_path: Path, *, output_name: str = "report.json") -> tuple[subprocess.CompletedProcess[str], Path]:
    assert BINARY.is_file(), f"required executable is missing: {BINARY}"
    input_path = tmp_path / "campaign.json"
    output_path = tmp_path / output_name
    input_path.write_text(json.dumps(campaign, allow_nan=False), encoding="utf-8")
    completed = _candidate_run(["--input", str(input_path), "--output", str(output_path)], timeout=30)
    return completed, output_path


def _read_valid_report(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    assert "NaN" not in text and "Infinity" not in text
    report = json.loads(text)

    def check_finite(value: object) -> None:
        if isinstance(value, float):
            assert math.isfinite(value)
        elif isinstance(value, list):
            for item in value:
                check_finite(item)
        elif isinstance(value, dict):
            for item in value.values():
                check_finite(item)

    check_finite(report)
    return report


def _assert_close(actual: float, expected: float, tolerance: float = 4e-6) -> None:
    assert actual == pytest.approx(expected, abs=tolerance, rel=tolerance)


@pytest.mark.parametrize("seed", range(101, 119), ids=lambda seed: f"equilibrium-{seed}")
def test_equilibrium_catalog_matches_the_energy_model(seed: int, tmp_path: Path) -> None:
    """Every queried load must contain all real equilibria with correct mechanics and ordering."""
    campaign = _campaign(seed)
    model = campaign["model"]

    # Exercise exact fold, exact stop-kink, and exact domain-boundary roots in addition to generic loads.
    folds = _folds(model)
    if folds:
        campaign["equilibrium_loads"][0] = _load_curve(model, folds[len(folds) // 2])
    if model["stops"]:
        campaign["equilibrium_loads"][1] = _load_curve(model, model["stops"][0]["angle"])
    campaign["equilibrium_loads"][2] = _load_curve(model, model["theta_min"])

    completed, output = _run(campaign, tmp_path)
    assert completed.returncode == 0, completed.stderr
    report = _read_valid_report(output)
    assert report["schema"] == "kirigami-snapthrough-v1"
    assert report["campaign"] == campaign["campaign"]
    assert len(report["equilibria"]) == len(campaign["equilibrium_loads"])

    for query, requested_load in zip(report["equilibria"], campaign["equilibrium_loads"], strict=True):
        _assert_close(query["load"], requested_load)
        expected_roots = _equilibria(model, requested_load)
        assert [state["theta"] for state in query["states"]] == sorted(state["theta"] for state in query["states"])
        assert len(query["states"]) == len(expected_roots)
        for state, theta in zip(query["states"], expected_roots, strict=True):
            _assert_close(state["theta"], theta)
            _assert_close(state["energy"], _energy(model, theta, requested_load), 2e-5)
            _assert_close(state["tangent_left"], _tangent(model, theta, requested_load, -1), 2e-5)
            _assert_close(state["tangent_right"], _tangent(model, theta, requested_load, 1), 2e-5)
            assert state["stability"] == _stability(model, theta, requested_load)
            assert state["active_stops"] == _active_indices(model, theta)
            assert all(type(index) is int for index in state["active_stops"])


@pytest.mark.parametrize("seed", [201, 202, 203, 204, 205, 206, 207, 208, 209, 210, 211, 212, 214, 215], ids=lambda seed: f"folds-{seed}")
def test_limit_points_are_all_and_only_smooth_extrema(seed: int, tmp_path: Path) -> None:
    """The limit-point list must exclude stop kinks and include every smooth strict extremum."""
    campaign = _campaign(seed)
    completed, output = _run(campaign, tmp_path)
    assert completed.returncode == 0, completed.stderr
    report = _read_valid_report(output)
    model = campaign["model"]
    expected = _folds(model)
    points = report["limit_points"]
    assert [point["theta"] for point in points] == sorted(point["theta"] for point in points)
    assert len(points) == len(expected)
    for point, theta in zip(points, expected, strict=True):
        _assert_close(point["theta"], theta)
        _assert_close(point["load"], _load_curve(model, theta))
        step = 1e-5 * (1.0 + abs(theta))
        center = _load_curve(model, theta)
        expected_type = (
            "maximum"
            if center > _load_curve(model, theta - step) and center > _load_curve(model, theta + step)
            else "minimum"
        )
        assert point["type"] == expected_type
        assert point["active_stops"] == _active_indices(model, theta)
        assert all(abs(theta - stop["angle"]) > 1e-7 for stop in model["stops"])


@pytest.mark.parametrize("seed", [301, 303, 304, 305, 307, 308, 310, 311, 312, 316, 318, 321], ids=lambda seed: f"sweep-{seed}")
def test_quasistatic_sweeps_follow_branches_and_snap(seed: int, tmp_path: Path) -> None:
    """Increasing and decreasing sweeps must reproduce branch continuation and directional snaps."""
    campaign = _campaign(seed, query_count=4, sweep_count=37)
    completed, output = _run(campaign, tmp_path)
    assert completed.returncode == 0, completed.stderr
    report = _read_valid_report(output)
    assert [item["id"] for item in report["sweeps"]] == [item["id"] for item in campaign["sweeps"]]
    for actual, requested in zip(report["sweeps"], campaign["sweeps"], strict=True):
        expected = _reference_sweep(campaign["model"], requested["loads"], requested["initial_theta"])
        assert len(actual["states"]) == len(expected)
        assert actual["states"][0]["transition"] == "initial"
        for state, reference in zip(actual["states"], expected, strict=True):
            _assert_close(state["load"], reference["load"])
            _assert_close(state["theta"], reference["theta"])
            _assert_close(state["energy"], reference["energy"], 2e-5)
            assert state["transition"] == reference["transition"]
        # Hidden campaigns are chosen to exercise at least one snap over the pair of sweeps.
    assert any(state["transition"] == "snap" for sweep_report in report["sweeps"] for state in sweep_report["states"])


def _base_invalid_campaign() -> dict:
    campaign = _campaign(411, query_count=3, sweep_count=9)
    campaign["campaign"] = "invalid-mutation-base"
    return campaign


def _invalid_variants() -> list[tuple[str, dict]]:
    base = _base_invalid_campaign()
    variants: list[tuple[str, dict]] = []

    def add(name: str, mutate) -> None:
        item = copy.deepcopy(base)
        mutate(item)
        variants.append((name, item))

    add("wrong-schema", lambda c: c.__setitem__("schema", "kirigami-campaign-v0"))
    add("empty-campaign", lambda c: c.__setitem__("campaign", ""))
    add("a1-range", lambda c: c["model"].__setitem__("a1", 50.1))
    add("a3-range", lambda c: c["model"].__setitem__("a3", -50.1))
    add("a5-nonpositive", lambda c: c["model"].__setitem__("a5", 0.0))
    add("b1-nonpositive", lambda c: c["model"].__setitem__("b1", 0.0))
    add("b3-negative", lambda c: c["model"].__setitem__("b3", -0.01))
    add("domain-too-narrow", lambda c: c["model"].__setitem__("theta_max", c["model"]["theta_min"] + 0.2))
    add("domain-too-wide", lambda c: c["model"].__setitem__("theta_max", c["model"]["theta_min"] + 8.1))
    add(
        "stop-on-boundary",
        lambda c: c["model"]["stops"].append(
            {"sense": "upper", "angle": c["model"]["theta_max"], "stiffness": 1.0}
        ),
    )
    add(
        "stop-zero-stiffness",
        lambda c: c["model"]["stops"].append({"sense": "upper", "angle": 0.1, "stiffness": 0.0}),
    )
    add(
        "stop-bad-sense",
        lambda c: c["model"]["stops"].append({"sense": "both", "angle": 0.1, "stiffness": 1.0}),
    )

    def duplicate_stop(campaign: dict) -> None:
        campaign["model"]["stops"] = [
            {"sense": "upper", "angle": 0.2, "stiffness": 1.0},
            {"sense": "upper", "angle": 0.2, "stiffness": 2.0},
        ]

    add("duplicate-stop", duplicate_stop)
    add("empty-equilibrium-loads", lambda c: c.__setitem__("equilibrium_loads", []))
    add("too-many-equilibrium-loads", lambda c: c.__setitem__("equilibrium_loads", [0.0] * 65))
    add("duplicate-sweep-id", lambda c: c["sweeps"][1].__setitem__("id", c["sweeps"][0]["id"]))
    add("one-load-sweep", lambda c: c["sweeps"][0].__setitem__("loads", [0.0]))
    add("nonmonotone-sweep", lambda c: c["sweeps"][0].__setitem__("loads", [0.0, 1.0, 0.5]))
    add("wrong-initial-state", lambda c: c["sweeps"][0].__setitem__("initial_theta", 0.123456789))
    return variants


@pytest.mark.parametrize("variant_name,campaign", _invalid_variants(), ids=lambda item: item if isinstance(item, str) else None)
def test_invalid_campaigns_preserve_existing_output(
    variant_name: str, campaign: dict, tmp_path: Path
) -> None:
    """Every malformed or inadmissible campaign must return 2 without changing prior output bytes."""
    del variant_name
    sentinel = b"previous validated report\x00\xff"
    output = tmp_path / "report.json"
    output.write_bytes(sentinel)
    original_inode = output.stat().st_ino
    completed, returned_output = _run(campaign, tmp_path)
    assert returned_output == output
    assert completed.returncode == 2
    assert output.read_bytes() == sentinel
    assert output.stat().st_ino == original_inode
    assert not list(tmp_path.glob(".*.tmp.*"))


@pytest.mark.parametrize(
    "arguments,input_text",
    [
        (["--input", "relative.json", "--output", "/tmp/out.json"], "{}"),
        (["--input", "/tmp/in.json", "--output", "relative.json"], "{}"),
        (["--input", "/tmp/in.json"], "{}"),
        (["--output", "/tmp/out.json"], "{}"),
        (["--unknown", "/tmp/in.json", "--output", "/tmp/out.json"], "{}"),
        (["--input", "/tmp/in.json", "--input", "/tmp/in.json", "--output", "/tmp/out.json"], "{}"),
        (["--input", "/tmp/in.json", "--output", "/tmp/out.json", "--output", "/tmp/out.json"], "{}"),
        (["--input", "/tmp/in.json", "--output", "/tmp/out.json"], "{broken"),
        (["--input", "/tmp/in.json", "--output", "/tmp/out.json"], '{"schema":"kirigami-campaign-v1","campaign":"x","model":{"a1":NaN}}'),
    ],
    ids=["relative-input", "relative-output", "missing-output", "missing-input", "unknown-flag", "duplicate-input", "duplicate-output", "malformed-json", "nan-token"],
)
def test_cli_and_json_rejections_return_two(arguments: list[str], input_text: str, tmp_path: Path) -> None:
    """The public CLI must reject incomplete flags, relative paths, malformed JSON, and non-finite tokens."""
    assert BINARY.is_file(), f"required executable is missing: {BINARY}"
    input_path = tmp_path / "in.json"
    output_path = tmp_path / "out.json"
    input_path.write_text(input_text, encoding="utf-8")
    resolved = [str(input_path) if value == "/tmp/in.json" else str(output_path) if value == "/tmp/out.json" else value for value in arguments]
    output_path.write_bytes(b"sentinel")
    completed = _candidate_run(resolved, timeout=10)
    assert completed.returncode == 2
    assert output_path.read_bytes() == b"sentinel"


@pytest.mark.parametrize("seed", [501, 502, 503])
def test_valid_runs_replace_output_without_temporary_artifacts(seed: int, tmp_path: Path) -> None:
    """A successful analysis must replace an existing report and leave no sibling temporary file."""
    campaign = _campaign(seed)
    output = tmp_path / "report.json"
    output.write_bytes(b"stale report")
    original_inode = output.stat().st_ino
    completed, returned_output = _run(campaign, tmp_path)
    assert completed.returncode == 0, completed.stderr
    assert returned_output == output
    report = _read_valid_report(output)
    assert report["campaign"] == campaign["campaign"]
    assert output.read_bytes() != b"stale report"
    assert output.stat().st_ino != original_inode
    assert not list(tmp_path.glob(".*.tmp.*"))


@pytest.mark.parametrize(
    "target_kind",
    ["docs-file", "cases-file", "docs-new", "cases-new", "docs-dotdot", "cases-dotdot", "docs-symlink", "cases-symlink"],
)
def test_protected_output_paths_return_two_without_modification(target_kind: str, tmp_path: Path) -> None:
    """Direct and aliased output paths inside the protected trees must be rejected before publication."""
    campaign = _campaign(509, query_count=3, sweep_count=9)
    input_path = tmp_path / "campaign.json"
    input_path.write_text(json.dumps(campaign, allow_nan=False), encoding="utf-8")

    if target_kind == "docs-file":
        output = APP_ROOT / "docs" / "analysis-contract.md"
    elif target_kind == "cases-file":
        output = APP_ROOT / "cases" / "bench-01.json"
    elif target_kind == "docs-new":
        output = APP_ROOT / "docs" / "generated-report.json"
    elif target_kind == "cases-new":
        output = APP_ROOT / "cases" / "nested" / "generated-report.json"
    elif target_kind == "docs-dotdot":
        output = APP_ROOT / "results" / ".." / "docs" / "analysis-contract.md"
    elif target_kind == "cases-dotdot":
        output = APP_ROOT / "results" / ".." / "cases" / "bench-01.json"
    else:
        link = tmp_path / "protected-link"
        link.symlink_to(APP_ROOT / ("docs" if target_kind == "docs-symlink" else "cases"), target_is_directory=True)
        output = link / ("analysis-contract.md" if target_kind == "docs-symlink" else "bench-01.json")

    existed = output.exists()
    before = output.read_bytes() if existed and output.is_file() else None
    inode = output.stat().st_ino if existed else None
    completed = _candidate_run(["--input", str(input_path), "--output", str(output)], timeout=10)
    assert completed.returncode == 2
    if existed:
        assert output.read_bytes() == before
        assert output.stat().st_ino == inode
    else:
        assert not output.exists()


def test_protected_contract_and_campaign_files_are_unchanged() -> None:
    """The authoritative mechanics contract and supplied campaigns must remain byte-for-byte unchanged."""
    for relative, expected_digest in PROTECTED_HASHES.items():
        path = APP_ROOT / relative
        assert path.is_file(), f"protected file is missing: {path}"
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected_digest, f"protected file changed: {path}"


def test_stress_campaign_covers_maximum_public_sizes(tmp_path: Path) -> None:
    """A valid maximum-size query and sweep must retain full numerical correctness without truncation."""
    campaign = _campaign(601, query_count=64, sweep_count=256)
    model = campaign["model"]
    # Expand to eight distinct unilateral stops while keeping the campaign admissible.
    model["stops"] = [
        {"sense": "lower" if index % 2 == 0 else "upper", "angle": -1.8 + index * 0.5, "stiffness": 0.6 + index * 0.4}
        for index in range(8)
    ]
    low, high = _load_span(model)
    campaign["equilibrium_loads"] = _linspace(low, high, 64)
    sweep_loads = _linspace(low, high, 256)
    campaign["sweeps"] = [
        {"id": "stress-up", "loads": sweep_loads, "initial_theta": min(_stable_roots(model, low))},
        {"id": "stress-down", "loads": list(reversed(sweep_loads)), "initial_theta": max(_stable_roots(model, high))},
    ]

    completed, output = _run(campaign, tmp_path)
    assert completed.returncode == 0, completed.stderr
    report = _read_valid_report(output)
    assert len(report["equilibria"]) == 64
    assert [len(item["states"]) for item in report["sweeps"]] == [256, 256]
    for index in [0, 15, 31, 47, 63]:
        load = campaign["equilibrium_loads"][index]
        expected = _equilibria(model, load)
        actual = report["equilibria"][index]["states"]
        assert len(actual) == len(expected)
        for state, theta in zip(actual, expected, strict=True):
            _assert_close(state["theta"], theta)
