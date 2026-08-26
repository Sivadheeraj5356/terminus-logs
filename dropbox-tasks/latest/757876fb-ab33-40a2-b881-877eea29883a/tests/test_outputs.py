from __future__ import annotations

import json
import math
import os
from pathlib import Path
import re
import stat
import subprocess

import pytest


ROOT = Path("/opt/foldpath")
BIN = Path("/usr/local/bin/foldpath")
CHECKER = Path("/usr/local/bin/foldmodel-check")
EXAMPLES = ROOT / "examples"

POINT_KEYS = {
    "type",
    "index",
    "arclength",
    "step_used",
    "lambda",
    "x",
    "residual_inf",
    "newton_iterations",
    "tangent",
    "fold",
}
SUMMARY_KEYS = {
    "type",
    "status",
    "dimension",
    "points",
    "folds",
    "arclength",
    "next_step",
}
NEGATIVE_ZERO = re.compile(
    r"(?<![0-9.eE+-])-0(?:\.0+)?(?:[eE][+-]?[0-9]+)?(?=[,\]\}\s])"
)


def execute(args: list[str | Path], *, timeout: float = 60.0) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(arg) for arg in args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
        env={**os.environ, "LC_ALL": "C", "LANG": "C"},
    )


@pytest.fixture(scope="session", autouse=True)
def rebuild_and_install() -> None:
    # Removing the installed command first makes this a source-build check, not a
    # check of an artifact left in the image or by a prior invocation.
    if BIN.is_file() or BIN.is_symlink():
        BIN.unlink()
    built = execute(["make", "-C", ROOT, "clean", "all", "install"], timeout=180.0)
    assert built.returncode == 0, (
        "source rebuild/install failed\n"
        f"stdout:\n{built.stdout}\nstderr:\n{built.stderr}"
    )


def assert_success(result: subprocess.CompletedProcess[str]) -> None:
    assert result.returncode == 0, (
        f"command exited {result.returncode}\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert result.stdout == ""
    assert result.stderr == ""


def assert_contract_error(result: subprocess.CompletedProcess[str], code: str) -> None:
    assert result.returncode == 2
    assert result.stdout == ""
    assert result.stderr == f'{{"error":"{code}"}}\n'


def assert_io_error(result: subprocess.CompletedProcess[str]) -> None:
    assert result.returncode == 4
    assert result.stdout == ""
    assert result.stderr == '{"error":"io_error"}\n'


def test_harness_session_dependencies_are_preinstalled_and_utf8_usable() -> None:
    """The image must start tmux and asciinema without an online setup repair."""
    environment = {**os.environ, "LC_ALL": "C.UTF-8", "LANG": "C.UTF-8"}
    probes = (("tmux", "-V"), ("asciinema", "--version"))
    for probe in probes:
        result = subprocess.run(
            probe,
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=5.0,
            check=False,
            env=environment,
        )
        assert result.returncode == 0, (
            f"{' '.join(probe)} is not usable without runner setup\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )


def parse_kv(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        stripped = raw.lstrip(" \t")
        if not stripped or stripped.startswith("#"):
            continue
        key, value = raw.split("=", 1)
        result[key.strip(" \t")] = value.strip(" \t")
    return result


def parsed_model(path: Path) -> dict[str, object]:
    raw = parse_kv(path)
    dimension = int(raw["dimension"])
    model: dict[str, object] = {
        "kind": raw["kind"],
        "dimension": dimension,
        "start_lambda": float(raw["start_lambda"]),
        "start_x": [float(item.strip()) for item in raw["start_x"].split(",")],
        "orientation": [
            float(item.strip()) for item in raw["orientation"].split(",")
        ],
    }
    for key in ("a", "bias", "coupling", "gain", "bias1", "bias2", "scale"):
        if key in raw:
            model[key] = float(raw[key])
    return model


def parsed_control(path: Path) -> dict[str, float | int]:
    raw = parse_kv(path)
    integers = {
        "fast_iterations",
        "slow_iterations",
        "max_newton_iterations",
        "max_points",
    }
    return {
        key: int(value) if key in integers else float(value)
        for key, value in raw.items()
    }


def write_control(path: Path, **changes: float | int) -> None:
    values: dict[str, float | int] = {
        "initial_step": 0.04,
        "min_step": 0.001,
        "max_step": 0.08,
        "grow_factor": 1.25,
        "shrink_factor": 0.5,
        "fast_iterations": 2,
        "slow_iterations": 6,
        "max_newton_iterations": 10,
        "residual_tolerance": 1e-11,
        "correction_tolerance": 1e-11,
        "fold_tangent_tolerance": 1e-5,
        "max_points": 12,
    }
    values.update(changes)
    path.write_text(
        "# Generated from the public control schema.\n"
        + "".join(f"{key}={value}\n" for key, value in values.items()),
        encoding="utf-8",
    )


def write_cubic_model(
    path: Path,
    *,
    x: float = -1.0,
    a: float = 1.0,
    bias: float = 0.0,
    orientation: tuple[float, float] = (1.0, 0.0),
) -> None:
    lam = bias - x * x * x + a * x
    path.write_text(
        "# A generated cubic branch, deliberately outside the included fixtures.\n"
        "kind = cubic\n"
        "dimension=1\n"
        f"start_lambda={lam:.17g}\n"
        f"start_x={x:.17g}\n"
        f"orientation={orientation[0]:.17g}, {orientation[1]:.17g}\n"
        f"a={a:.17g}\n"
        f"bias={bias:.17g}\n",
        encoding="utf-8",
    )


def write_coupled_model(
    path: Path,
    *,
    x0: float,
    a: float,
    coupling: float,
    gain: float,
    bias1: float,
    bias2: float,
) -> None:
    x1 = gain * x0 * x0 + bias2
    lam = bias1 - x0 * x0 * x0 + a * x0 - coupling * x1
    path.write_text(
        "# Whitespace around keys and vector items is part of the public input syntax.\n"
        " kind = coupled\n"
        "dimension = 2\n"
        f"start_lambda = {lam:.17g}\n"
        f"start_x = {x0:.17g}, {x1:.17g}\n"
        "orientation = 1, 0, 0\n"
        f"a = {a:.17g}\n"
        f"coupling = {coupling:.17g}\n"
        f"gain = {gain:.17g}\n"
        f"bias1 = {bias1:.17g}\n"
        f"bias2 = {bias2:.17g}\n",
        encoding="utf-8",
    )


def write_bratu_model(path: Path, *, dimension: int, scale: float) -> None:
    zeros = ",".join("0" for _ in range(dimension))
    orientation = ",".join([*("0" for _ in range(dimension)), "1"])
    path.write_text(
        "kind=bratu\n"
        f"dimension={dimension}\n"
        "start_lambda=0\n"
        f"start_x={zeros}\n"
        f"orientation={orientation}\n"
        f"scale={scale:.17g}\n",
        encoding="utf-8",
    )


def invoke(
    mode: str,
    model: Path,
    control: Path,
    output: Path,
    checkpoint: Path,
    *,
    accept_limit: int | None = None,
) -> subprocess.CompletedProcess[str]:
    # The non-declaration order also checks the documented order-independent option parser.
    args: list[str | Path] = [
        BIN,
        mode,
        "--checkpoint",
        checkpoint,
        "--model",
        model,
        "--output",
        output,
        "--control",
        control,
    ]
    if accept_limit is not None:
        args.extend(["--accept-limit", str(accept_limit)])
    return execute(args)


def finite_number(value: object, label: str) -> float:
    assert isinstance(value, (int, float)) and not isinstance(value, bool), label
    converted = float(value)
    assert math.isfinite(converted), label
    return converted


def load_trace(path: Path) -> tuple[list[dict[str, object]], dict[str, object]]:
    raw = path.read_bytes()
    assert raw.endswith(b"\n"), "NDJSON must end in a newline"
    assert not raw.endswith(b"\n\n"), "NDJSON must end in exactly one newline"
    text = raw.decode("utf-8")
    assert NEGATIVE_ZERO.search(text) is None, "negative zero must be serialized as 0"
    lines = text[:-1].split("\n")
    assert lines and all(lines), "blank NDJSON records are not allowed"

    def reject_constant(token: str) -> object:
        raise ValueError(f"non-finite JSON token: {token}")

    records = [json.loads(line, parse_constant=reject_constant) for line in lines]
    assert all(isinstance(record, dict) for record in records)
    assert len(records) >= 2
    points = records[:-1]
    summary = records[-1]
    assert all(record.get("type") == "point" for record in points)
    assert summary.get("type") == "summary"
    return points, summary


def evaluate(
    model: dict[str, object], x: list[float], lam: float
) -> tuple[list[float], list[list[float]], list[float]]:
    n = int(model["dimension"])
    kind = model["kind"]
    if kind == "cubic":
        a = float(model["a"])
        bias = float(model["bias"])
        return (
            [x[0] * x[0] * x[0] - a * x[0] + lam - bias],
            [[3.0 * x[0] * x[0] - a]],
            [1.0],
        )
    if kind == "coupled":
        a = float(model["a"])
        coupling = float(model["coupling"])
        gain = float(model["gain"])
        bias1 = float(model["bias1"])
        bias2 = float(model["bias2"])
        return (
            [
                x[0] * x[0] * x[0] - a * x[0] + lam + coupling * x[1] - bias1,
                x[1] - gain * x[0] * x[0] - bias2,
            ],
            [
                [3.0 * x[0] * x[0] - a, coupling],
                [-2.0 * gain * x[0], 1.0],
            ],
            [1.0, 0.0],
        )
    assert kind == "bratu"
    scale = float(model["scale"])
    h = 1.0 / (n + 1.0)
    factor = scale / (h * h)
    residual: list[float] = []
    jacobian = [[0.0 for _ in range(n)] for _ in range(n)]
    parameter: list[float] = []
    for i in range(n):
        exponential = math.exp(x[i])
        left = x[i - 1] if i > 0 else 0.0
        right = x[i + 1] if i + 1 < n else 0.0
        residual.append(factor * (left - 2.0 * x[i] + right) + lam * exponential)
        jacobian[i][i] = -2.0 * factor + lam * exponential
        if i > 0:
            jacobian[i][i - 1] = factor
        if i + 1 < n:
            jacobian[i][i + 1] = factor
        parameter.append(exponential)
    return residual, jacobian, parameter


def solve_linear(matrix: list[list[float]], rhs: list[float]) -> list[float]:
    """Independent small dense solve used only for generated first-step checks."""
    n = len(rhs)
    augmented = [row[:] + [rhs[i]] for i, row in enumerate(matrix)]
    for column in range(n):
        pivot = max(range(column, n), key=lambda row: abs(augmented[row][column]))
        assert abs(augmented[pivot][column]) > 1e-15
        augmented[column], augmented[pivot] = augmented[pivot], augmented[column]
        for row in range(column + 1, n):
            multiplier = augmented[row][column] / augmented[column][column]
            for item in range(column, n + 1):
                augmented[row][item] -= multiplier * augmented[column][item]
    answer = [0.0] * n
    for row in range(n - 1, -1, -1):
        answer[row] = (
            augmented[row][n]
            - sum(augmented[row][column] * answer[column] for column in range(row + 1, n))
        ) / augmented[row][row]
    return answer


def normalized(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in vector))
    assert norm > 0.0 and math.isfinite(norm)
    return [value / norm for value in vector]


def independent_initial_tangent(model: dict[str, object]) -> list[float]:
    x = list(model["start_x"])
    lam = float(model["start_lambda"])
    _, jacobian, parameter = evaluate(model, x, lam)
    tangent = normalized(solve_linear(jacobian, [-value for value in parameter]) + [1.0])
    orientation = list(model["orientation"])
    if sum(a * b for a, b in zip(tangent, orientation)) < 0.0:
        tangent = [-value for value in tangent]
    return tangent


def independent_first_step(
    model: dict[str, object], control: dict[str, float | int], step: float | None = None
) -> tuple[list[float], list[float], int, float]:
    """Compute one documented predictor/corrector step, not a full trace generator."""
    n = int(model["dimension"])
    previous = list(model["start_x"]) + [float(model["start_lambda"])]
    old_tangent = independent_initial_tangent(model)
    ds = float(control["initial_step"] if step is None else step)
    predictor = [value + ds * direction for value, direction in zip(previous, old_tangent)]
    corrected = predictor[:]
    iterations = 0
    while True:
        residual, jacobian, parameter = evaluate(model, corrected[:n], corrected[n])
        plane_error = sum(
            old_tangent[i] * (corrected[i] - predictor[i]) for i in range(n + 1)
        )
        if (
            max(abs(value) for value in residual) <= float(control["residual_tolerance"])
            and abs(plane_error) <= float(control["correction_tolerance"])
        ):
            break
        assert iterations < int(control["max_newton_iterations"])
        matrix = [jacobian[row] + [parameter[row]] for row in range(n)]
        matrix.append(old_tangent[:])
        delta = solve_linear(matrix, [-value for value in residual] + [-plane_error])
        corrected = [value + change for value, change in zip(corrected, delta)]
        iterations += 1
    residual, jacobian, parameter = evaluate(model, corrected[:n], corrected[n])
    tangent_matrix = [jacobian[row] + [parameter[row]] for row in range(n)]
    tangent_matrix.append(old_tangent[:])
    tangent = normalized(solve_linear(tangent_matrix, [0.0] * n + [1.0]))
    if sum(a * b for a, b in zip(tangent, old_tangent)) < 0.0:
        tangent = [-value for value in tangent]
    return corrected, tangent, iterations, max(abs(value) for value in residual)


def independent_step(
    model: dict[str, object],
    control: dict[str, float | int],
    previous_y: list[float],
    previous_tangent: list[float],
    attempted_step: float,
) -> tuple[list[float], list[float], int, float]:
    """Independently execute one arbitrary documented continuation attempt."""
    n = int(model["dimension"])
    predictor = [
        value + attempted_step * direction
        for value, direction in zip(previous_y, previous_tangent)
    ]
    corrected = predictor[:]
    iterations = 0
    while True:
        residual, jacobian, parameter = evaluate(model, corrected[:n], corrected[n])
        plane_error = sum(
            previous_tangent[i] * (corrected[i] - predictor[i])
            for i in range(n + 1)
        )
        if (
            max(abs(value) for value in residual)
            <= float(control["residual_tolerance"])
            and abs(plane_error) <= float(control["correction_tolerance"])
        ):
            break
        if iterations == int(control["max_newton_iterations"]):
            raise ArithmeticError("reference corrector did not converge")
        matrix = [jacobian[row] + [parameter[row]] for row in range(n)]
        matrix.append(previous_tangent[:])
        delta = solve_linear(matrix, [-value for value in residual] + [-plane_error])
        corrected = [value + change for value, change in zip(corrected, delta)]
        if not all(math.isfinite(value) for value in corrected):
            raise ArithmeticError("non-finite reference correction")
        iterations += 1

    residual, jacobian, parameter = evaluate(model, corrected[:n], corrected[n])
    tangent_matrix = [jacobian[row] + [parameter[row]] for row in range(n)]
    tangent_matrix.append(previous_tangent[:])
    tangent = normalized(solve_linear(tangent_matrix, [0.0] * n + [1.0]))
    if sum(a * b for a, b in zip(tangent, previous_tangent)) < 0.0:
        tangent = [-value for value in tangent]
    return corrected, tangent, iterations, max(abs(value) for value in residual)


def independent_trace(
    model_path: Path, control_path: Path
) -> tuple[list[dict[str, object]], dict[str, object]]:
    """Small independent full-trace oracle for generated, well-conditioned cases."""
    model = parsed_model(model_path)
    control = parsed_control(control_path)
    n = int(model["dimension"])
    y = list(model["start_x"]) + [float(model["start_lambda"])]
    tangent = independent_initial_tangent(model)
    residual, _, _ = evaluate(model, y[:n], y[n])
    points: list[dict[str, object]] = [
        {
            "type": "point",
            "index": 0,
            "arclength": 0.0,
            "step_used": 0.0,
            "lambda": y[n],
            "x": y[:n],
            "residual_inf": max(abs(value) for value in residual),
            "newton_iterations": 0,
            "tangent": tangent,
            "fold": "none",
        }
    ]
    retained = tangent_class(tangent[n], float(control["fold_tangent_tolerance"]))
    if retained == "zero":
        retained = None
    folds = 0
    arclength = 0.0
    next_step = float(control["initial_step"])

    while len(points) < int(control["max_points"]):
        step = next_step
        while True:
            try:
                corrected, next_tangent, iterations, residual_inf = independent_step(
                    model, control, y, tangent, step
                )
                break
            except (ArithmeticError, AssertionError, OverflowError):
                if step == float(control["min_step"]):
                    raise AssertionError("generated oracle case unexpectedly stalled")
                step = max(
                    float(control["min_step"]),
                    step * float(control["shrink_factor"]),
                )

        arclength += math.hypot(
            *(new - old for new, old in zip(corrected, y))
        )
        current = tangent_class(
            next_tangent[n], float(control["fold_tangent_tolerance"])
        )
        fold = "none"
        if current != "zero":
            if retained is not None and current != retained:
                fold = "max_lambda" if retained == "positive" else "min_lambda"
                folds += 1
            retained = current
        points.append(
            {
                "type": "point",
                "index": len(points),
                "arclength": arclength,
                "step_used": step,
                "lambda": corrected[n],
                "x": corrected[:n],
                "residual_inf": residual_inf,
                "newton_iterations": iterations,
                "tangent": next_tangent,
                "fold": fold,
            }
        )
        if iterations <= int(control["fast_iterations"]):
            next_step = min(
                float(control["max_step"]), step * float(control["grow_factor"])
            )
        elif iterations >= int(control["slow_iterations"]):
            next_step = max(
                float(control["min_step"]), step * float(control["shrink_factor"])
            )
        else:
            next_step = step
        y = corrected
        tangent = next_tangent

    return points, {
        "type": "summary",
        "status": "complete",
        "dimension": n,
        "points": len(points),
        "folds": folds,
        "arclength": arclength,
        "next_step": next_step,
    }


def assert_trace_matches_oracle(
    actual: tuple[list[dict[str, object]], dict[str, object]],
    expected: tuple[list[dict[str, object]], dict[str, object]],
) -> None:
    actual_points, actual_summary = actual
    expected_points, expected_summary = expected
    assert len(actual_points) == len(expected_points)
    for got, wanted in zip(actual_points, expected_points):
        assert got["index"] == wanted["index"]
        assert got["fold"] == wanted["fold"]
        assert got["newton_iterations"] == wanted["newton_iterations"]
        for key in ("arclength", "step_used", "lambda", "residual_inf"):
            assert float(got[key]) == pytest.approx(
                float(wanted[key]), rel=3e-9, abs=4e-11
            )
        assert got["x"] == pytest.approx(wanted["x"], rel=3e-9, abs=4e-11)
        assert got["tangent"] == pytest.approx(
            wanted["tangent"], rel=3e-9, abs=4e-11
        )
    for key in ("status", "dimension", "points", "folds"):
        assert actual_summary[key] == expected_summary[key]
    for key in ("arclength", "next_step"):
        assert float(actual_summary[key]) == pytest.approx(
            float(expected_summary[key]), rel=3e-9, abs=4e-11
        )


def close(actual: float, expected: float, *, absolute: float = 2e-10) -> bool:
    return math.isclose(actual, expected, rel_tol=2e-9, abs_tol=absolute)


def retry_step_matches(actual: float, attempted: float, minimum: float, shrink: float) -> bool:
    candidate = attempted
    for _ in range(128):
        if close(actual, candidate, absolute=2e-12):
            return True
        if close(candidate, minimum, absolute=2e-12):
            return False
        candidate = max(minimum, candidate * shrink)
    return False


def tangent_class(value: float, tolerance: float) -> str:
    if value > tolerance:
        return "positive"
    if value < -tolerance:
        return "negative"
    return "zero"


def validate_trace(
    output: Path,
    model_path: Path,
    control_path: Path,
    *,
    expected_status: str | None = None,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    model = parsed_model(model_path)
    control = parsed_control(control_path)
    n = int(model["dimension"])
    points, summary = load_trace(output)

    assert set(summary) == SUMMARY_KEYS
    assert summary["status"] in {"partial", "complete", "stalled"}
    if expected_status is not None:
        assert summary["status"] == expected_status
    assert isinstance(summary["dimension"], int) and not isinstance(
        summary["dimension"], bool
    )
    assert isinstance(summary["points"], int) and not isinstance(summary["points"], bool)
    assert summary["dimension"] == n
    assert summary["points"] == len(points)
    assert isinstance(summary["folds"], int) and not isinstance(summary["folds"], bool)
    assert summary["folds"] >= 0
    finite_number(summary["arclength"], "summary arclength")
    finite_number(summary["next_step"], "summary next_step")
    if summary["status"] == "complete":
        assert len(points) == int(control["max_points"])
    else:
        assert len(points) < int(control["max_points"])

    retained: str | None = None
    fold_count = 0
    next_attempt = float(control["initial_step"])
    previous_y: list[float] | None = None
    previous_arclength = 0.0
    previous_tangent: list[float] | None = None
    fold_tolerance = float(control["fold_tangent_tolerance"])

    for index, point in enumerate(points):
        assert set(point) == POINT_KEYS
        assert point["type"] == "point"
        assert point["index"] == index
        assert isinstance(point["index"], int) and not isinstance(point["index"], bool)
        assert isinstance(point["newton_iterations"], int) and not isinstance(
            point["newton_iterations"], bool
        )
        assert point["fold"] in {"none", "max_lambda", "min_lambda"}
        assert isinstance(point["x"], list) and len(point["x"]) == n
        assert isinstance(point["tangent"], list) and len(point["tangent"]) == n + 1
        x = [finite_number(value, f"point {index} x") for value in point["x"]]
        lam = finite_number(point["lambda"], f"point {index} lambda")
        tangent = [
            finite_number(value, f"point {index} tangent") for value in point["tangent"]
        ]
        arclength = finite_number(point["arclength"], f"point {index} arclength")
        step_used = finite_number(point["step_used"], f"point {index} step")
        reported_residual = finite_number(
            point["residual_inf"], f"point {index} residual"
        )
        residual, jacobian, parameter = evaluate(model, x, lam)
        actual_residual = max(abs(value) for value in residual)
        numeric_scale = max(
            1.0,
            abs(lam),
            *(abs(value) for value in x),
            *(abs(value) for value in residual),
        )
        residual_roundoff = 32.0 * (n + 1) * math.ulp(numeric_scale)
        assert abs(reported_residual - actual_residual) <= residual_roundoff
        assert actual_residual <= float(control["residual_tolerance"]) + residual_roundoff
        assert close(math.sqrt(sum(value * value for value in tangent)), 1.0, absolute=2e-9)
        null_residual = max(
            abs(
                sum(jacobian[row][column] * tangent[column] for column in range(n))
                + parameter[row] * tangent[n]
            )
            for row in range(n)
        )
        matrix_scale = max(
            1.0,
            *(abs(value) for row in jacobian for value in row),
            *(abs(value) for value in parameter),
        )
        assert null_residual <= 2e-8 * matrix_scale

        current_class = tangent_class(tangent[-1], fold_tolerance)
        if index == 0:
            assert x == pytest.approx(model["start_x"], rel=0.0, abs=2e-14)
            assert close(lam, float(model["start_lambda"]), absolute=2e-14)
            assert arclength == 0.0
            assert step_used == 0.0
            assert point["newton_iterations"] == 0
            assert point["fold"] == "none"
            initial = independent_initial_tangent(model)
            assert tangent == pytest.approx(initial, rel=2e-9, abs=2e-10)
            if current_class != "zero":
                retained = current_class
        else:
            assert previous_y is not None and previous_tangent is not None
            assert step_used > 0.0
            assert retry_step_matches(
                step_used,
                next_attempt,
                float(control["min_step"]),
                float(control["shrink_factor"]),
            ), f"point {index} did not use a documented retry step"
            predictor = [
                previous_y[item] + step_used * previous_tangent[item]
                for item in range(n + 1)
            ]
            plane_error = abs(
                sum(
                    previous_tangent[item]
                    * ((x + [lam])[item] - predictor[item])
                    for item in range(n + 1)
                )
            )
            plane_scale = max(
                1.0,
                *(abs(value) for value in predictor),
                *(abs(value) for value in x + [lam]),
            )
            plane_roundoff = 32.0 * (n + 1) * math.ulp(plane_scale)
            assert (
                plane_error
                <= float(control["correction_tolerance"]) + plane_roundoff
            )
            distance = math.sqrt(
                sum((a - b) ** 2 for a, b in zip(x + [lam], previous_y))
            )
            assert close(arclength, previous_arclength + distance, absolute=3e-10)
            assert sum(a * b for a, b in zip(tangent, previous_tangent)) >= -2e-10
            expected_fold = "none"
            if current_class != "zero":
                if retained is not None and retained != current_class:
                    expected_fold = (
                        "max_lambda" if retained == "positive" else "min_lambda"
                    )
                    fold_count += 1
                retained = current_class
            assert point["fold"] == expected_fold

            iterations = int(point["newton_iterations"])
            assert 0 <= iterations <= int(control["max_newton_iterations"])
            if iterations <= int(control["fast_iterations"]):
                next_attempt = min(
                    float(control["max_step"]), step_used * float(control["grow_factor"])
                )
            elif iterations >= int(control["slow_iterations"]):
                next_attempt = max(
                    float(control["min_step"]),
                    step_used * float(control["shrink_factor"]),
                )
            else:
                next_attempt = step_used

        previous_y = x + [lam]
        previous_tangent = tangent
        previous_arclength = arclength

    assert summary["folds"] == fold_count
    assert close(float(summary["arclength"]), previous_arclength, absolute=2e-10)
    if summary["status"] != "stalled":
        assert close(float(summary["next_step"]), next_attempt, absolute=2e-12)
    return points, summary


def test_source_rebuild_installs_a_regular_native_command_and_keeps_checker() -> None:
    """The clean source build must install native commands without replacing the checker."""
    assert BIN.exists()
    assert not BIN.is_symlink()
    mode = BIN.stat().st_mode
    assert stat.S_ISREG(mode)
    assert mode & 0o111
    assert BIN.read_bytes()[:4] == b"\x7fELF"
    assert list(ROOT.rglob("*.c")), "the installed command must be built from C source"

    checked = execute(
        [
            CHECKER,
            "--model",
            EXAMPLES / "cubic.model",
            "--control",
            EXAMPLES / "standard.control",
        ]
    )
    assert checked.returncode == 0, checked.stdout + checked.stderr
    assert checked.stderr == ""
    semantic = json.loads(checked.stdout)
    assert isinstance(semantic, dict) and semantic


def test_included_cubic_fixture_emits_a_valid_limited_trace(tmp_path: Path) -> None:
    """A shipped cubic input must produce a clean partial trace and checkpoint."""
    model = EXAMPLES / "cubic.model"
    control = EXAMPLES / "standard.control"
    output = tmp_path / "included.ndjson"
    checkpoint = tmp_path / "included.state"
    result = invoke("run", model, control, output, checkpoint, accept_limit=5)
    assert_success(result)
    control_values = parsed_control(control)
    expected_points = min(6, int(control_values["max_points"]))
    expected_status = "complete" if expected_points == int(control_values["max_points"]) else "partial"
    points, _ = validate_trace(
        output, model, control, expected_status=expected_status
    )
    assert len(points) == expected_points
    assert checkpoint.is_file() and checkpoint.stat().st_size > 0
    assert set(tmp_path.iterdir()) == {output, checkpoint}


@pytest.mark.parametrize("kind", ["coupled", "bratu"])
def test_generated_models_match_equations_and_an_independent_first_step(
    tmp_path: Path, kind: str
) -> None:
    """Generated non-cubic models must match their equations and first corrector step."""
    model = tmp_path / f"generated-{kind}.model"
    control = tmp_path / f"generated-{kind}.control"
    if kind == "coupled":
        write_coupled_model(
            model,
            x0=0.17,
            a=1.35,
            coupling=-0.28,
            gain=0.43,
            bias1=0.21,
            bias2=-0.06,
        )
    else:
        write_bratu_model(model, dimension=4, scale=0.73)
    write_control(
        control,
        initial_step=0.025,
        min_step=0.001,
        max_step=0.05,
        residual_tolerance=1e-12,
        correction_tolerance=1e-12,
        max_points=9,
    )
    output = tmp_path / f"{kind}.ndjson"
    checkpoint = tmp_path / f"{kind}.state"
    result = invoke("run", model, control, output, checkpoint, accept_limit=3)
    assert_success(result)
    points, summary = validate_trace(output, model, control, expected_status="partial")
    assert len(points) == 4
    assert summary["points"] == 4

    expected_y, expected_tangent, expected_iterations, expected_residual = independent_first_step(
        parsed_model(model), parsed_control(control)
    )
    actual_y = [float(value) for value in points[1]["x"]] + [float(points[1]["lambda"])]
    actual_tangent = [float(value) for value in points[1]["tangent"]]
    assert actual_y == pytest.approx(expected_y, rel=3e-9, abs=3e-10)
    assert actual_tangent == pytest.approx(expected_tangent, rel=3e-9, abs=3e-10)
    assert points[1]["newton_iterations"] == expected_iterations
    assert float(points[1]["residual_inf"]) == pytest.approx(
        expected_residual, rel=3e-8, abs=3e-13
    )


@pytest.mark.parametrize("kind", ["reverse_coupled", "bratu8"])
def test_generated_full_traces_match_an_independent_multistep_oracle(
    tmp_path: Path, kind: str
) -> None:
    """Reverse and high-dimensional traces must match an independent full oracle."""
    model = tmp_path / f"oracle-{kind}.model"
    control = tmp_path / f"oracle-{kind}.control"
    if kind == "reverse_coupled":
        write_coupled_model(
            model,
            x0=0.38,
            a=1.61,
            coupling=-0.37,
            gain=0.29,
            bias1=0.14,
            bias2=-0.08,
        )
        text = model.read_text(encoding="utf-8")
        model.write_text(
            text.replace("orientation = 1, 0, 0", "orientation = -0.8, 0.3, -0.2"),
            encoding="utf-8",
        )
        write_control(
            control,
            initial_step=0.031,
            min_step=0.0005,
            max_step=0.079,
            grow_factor=1.31,
            shrink_factor=0.43,
            fast_iterations=2,
            slow_iterations=5,
            max_newton_iterations=13,
            residual_tolerance=3e-12,
            correction_tolerance=2e-12,
            fold_tangent_tolerance=0.035,
            max_points=19,
        )
    else:
        write_bratu_model(model, dimension=8, scale=0.61)
        write_control(
            control,
            initial_step=0.018,
            min_step=0.0002,
            max_step=0.047,
            grow_factor=1.27,
            shrink_factor=0.47,
            fast_iterations=2,
            slow_iterations=6,
            max_newton_iterations=15,
            residual_tolerance=2e-11,
            correction_tolerance=7e-12,
            fold_tangent_tolerance=0.04,
            max_points=17,
        )

    output = tmp_path / f"oracle-{kind}.ndjson"
    checkpoint = tmp_path / f"oracle-{kind}.state"
    result = invoke("run", model, control, output, checkpoint)
    assert_success(result)
    actual = validate_trace(output, model, control, expected_status="complete")
    expected = independent_trace(model, control)
    assert_trace_matches_oracle(actual, expected)


def test_cubic_continuation_traverses_both_turning_points_in_acceptance_order(
    tmp_path: Path,
) -> None:
    """Continuation must cross both folds without sorting points by parameter value."""
    model = tmp_path / "two-folds.model"
    control = tmp_path / "two-folds.control"
    write_cubic_model(model, x=-1.0, a=1.0, bias=0.0)
    write_control(
        control,
        initial_step=0.07,
        min_step=0.001,
        max_step=0.11,
        grow_factor=1.15,
        fast_iterations=3,
        slow_iterations=8,
        max_newton_iterations=12,
        residual_tolerance=1e-12,
        correction_tolerance=1e-12,
        fold_tangent_tolerance=0.2,
        max_points=42,
    )
    output = tmp_path / "two-folds.ndjson"
    checkpoint = tmp_path / "two-folds.state"
    result = invoke("run", model, control, output, checkpoint)
    assert_success(result)
    points, summary = validate_trace(output, model, control, expected_status="complete")
    labels = [point["fold"] for point in points if point["fold"] != "none"]
    assert labels == ["min_lambda", "max_lambda"]
    assert summary["folds"] == 2
    classes = [
        tangent_class(float(point["tangent"][-1]), 0.2) for point in points
    ]
    fold_indices = [index for index, point in enumerate(points) if point["fold"] != "none"]
    assert any(value == "zero" for value in classes[: fold_indices[0]])
    assert any(
        value == "zero" for value in classes[fold_indices[0] + 1 : fold_indices[1]]
    )
    lambdas = [float(point["lambda"]) for point in points]
    changes = [b - a for a, b in zip(lambdas, lambdas[1:])]
    assert any(change < -1e-5 for change in changes)
    assert any(change > 1e-5 for change in changes)
    # Acceptance order follows increasing x on this orientation, not sorted lambda.
    xs = [float(point["x"][0]) for point in points]
    assert all(a < b for a, b in zip(xs, xs[1:]))
    assert lambdas != sorted(lambdas)


def test_rejected_predictors_shrink_before_acceptance_and_drive_slow_adaptation(
    tmp_path: Path,
) -> None:
    """Rejected attempts must shrink locally and accepted slow steps must adapt."""
    model = tmp_path / "rejection.model"
    control = tmp_path / "rejection.control"
    write_cubic_model(model, x=-0.6, a=1.0)
    write_control(
        control,
        initial_step=0.4,
        min_step=0.00625,
        max_step=0.4,
        grow_factor=2.0,
        shrink_factor=0.5,
        fast_iterations=0,
        slow_iterations=1,
        max_newton_iterations=1,
        residual_tolerance=1e-8,
        correction_tolerance=1e-10,
        max_points=5,
    )
    output = tmp_path / "rejection.ndjson"
    checkpoint = tmp_path / "rejection.state"
    result = invoke("run", model, control, output, checkpoint, accept_limit=1)
    assert_success(result)
    points, summary = validate_trace(output, model, control, expected_status="partial")
    assert len(points) == 2
    assert float(points[1]["step_used"]) == pytest.approx(0.0125, rel=0.0, abs=2e-14)
    assert points[1]["newton_iterations"] == 1
    assert float(summary["next_step"]) == pytest.approx(0.00625, rel=0.0, abs=2e-14)


def test_failure_at_minimum_step_persists_a_stalled_initial_history(tmp_path: Path) -> None:
    """Failure at the minimum step must persist the last history with stalled status."""
    model = tmp_path / "stall.model"
    control = tmp_path / "stall.control"
    write_cubic_model(model, x=-0.6, a=1.0)
    write_control(
        control,
        initial_step=0.4,
        min_step=0.4,
        max_step=0.4,
        grow_factor=2.0,
        shrink_factor=0.5,
        fast_iterations=0,
        slow_iterations=1,
        max_newton_iterations=1,
        residual_tolerance=1e-10,
        correction_tolerance=1e-10,
        max_points=5,
    )
    output = tmp_path / "stall.ndjson"
    checkpoint = tmp_path / "stall.state"
    result = invoke("run", model, control, output, checkpoint)
    assert result.returncode == 3
    assert result.stdout == ""
    assert result.stderr == ""
    points, summary = validate_trace(output, model, control, expected_status="stalled")
    assert len(points) == 1
    assert summary["folds"] == 0
    assert float(summary["next_step"]) == pytest.approx(0.4)
    assert checkpoint.is_file() and checkpoint.stat().st_size > 0


def test_checkpoint_split_and_multiple_resumes_equal_an_uninterrupted_trace(
    tmp_path: Path,
) -> None:
    """Multiple resumptions must be semantically identical to one uninterrupted run."""
    model = tmp_path / "resume.model"
    control = tmp_path / "resume.control"
    write_cubic_model(model, x=-1.0, a=1.0, bias=0.125)
    write_control(
        control,
        initial_step=0.075,
        max_step=0.105,
        grow_factor=1.2,
        fast_iterations=3,
        slow_iterations=8,
        max_newton_iterations=12,
        residual_tolerance=1e-12,
        correction_tolerance=1e-12,
        fold_tangent_tolerance=0.01,
        max_points=30,
    )
    split_output = tmp_path / "split.ndjson"
    split_checkpoint = tmp_path / "split.state"
    whole_output = tmp_path / "whole.ndjson"
    whole_checkpoint = tmp_path / "whole.state"

    first = invoke(
        "run", model, control, split_output, split_checkpoint, accept_limit=6
    )
    assert_success(first)
    first_points, _ = validate_trace(
        split_output, model, control, expected_status="partial"
    )
    assert len(first_points) == 7
    split_output.write_bytes(b"this stale output must not be used as resume state\n")

    second = invoke(
        "resume", model, control, split_output, split_checkpoint, accept_limit=5
    )
    assert_success(second)
    second_points, _ = validate_trace(
        split_output, model, control, expected_status="partial"
    )
    assert len(second_points) == 12
    split_output.unlink()

    completed = invoke("resume", model, control, split_output, split_checkpoint)
    assert_success(completed)
    split_trace = validate_trace(
        split_output, model, control, expected_status="complete"
    )

    uninterrupted = invoke("run", model, control, whole_output, whole_checkpoint)
    assert_success(uninterrupted)
    whole_trace = validate_trace(
        whole_output, model, control, expected_status="complete"
    )
    assert split_trace == whole_trace

    idempotent = invoke("resume", model, control, split_output, split_checkpoint)
    assert_success(idempotent)
    assert validate_trace(
        split_output, model, control, expected_status="complete"
    ) == split_trace


def test_input_usage_and_path_errors_preserve_existing_artifacts(tmp_path: Path) -> None:
    """Malformed inputs, relative paths, and conflicts must preserve existing bytes."""
    model = tmp_path / "input.model"
    control = tmp_path / "input.control"
    output = tmp_path / "old.ndjson"
    checkpoint = tmp_path / "old.state"
    write_cubic_model(model, x=-0.9, a=1.1)
    write_control(control, max_points=8)
    original_model = model.read_bytes()
    output.write_bytes(b"old-output\x00bytes")
    checkpoint.write_bytes(b"old-checkpoint\xffbytes")
    old_output = output.read_bytes()
    old_checkpoint = checkpoint.read_bytes()

    model.write_text(model.read_text(encoding="utf-8") + "unknown_key=7\n", encoding="utf-8")
    invalid_model = invoke("run", model, control, output, checkpoint)
    assert_contract_error(invalid_model, "model_invalid")
    assert output.read_bytes() == old_output
    assert checkpoint.read_bytes() == old_checkpoint

    model.write_bytes(original_model)
    valid_control = control.read_bytes()
    control.write_bytes(valid_control + b"max_points=9\n")
    invalid_control = invoke("run", model, control, output, checkpoint)
    assert_contract_error(invalid_control, "control_invalid")
    assert output.read_bytes() == old_output
    assert checkpoint.read_bytes() == old_checkpoint
    control.write_bytes(valid_control)

    relative = execute(
        [
            BIN,
            "run",
            "--model",
            "relative.model",
            "--control",
            control,
            "--output",
            output,
            "--checkpoint",
            checkpoint,
        ]
    )
    assert_contract_error(relative, "usage")
    assert output.read_bytes() == old_output
    assert checkpoint.read_bytes() == old_checkpoint

    shared = tmp_path / "shared-artifact"
    shared.write_bytes(b"shared bytes")
    conflict = invoke("run", model, control, shared, shared)
    assert_contract_error(conflict, "path_conflict")
    assert shared.read_bytes() == b"shared bytes"

    # The input path is also one of the four pairwise-distinct public path strings.
    input_alias = invoke("run", model, control, model, checkpoint)
    assert_contract_error(input_alias, "path_conflict")
    assert model.read_bytes() == original_model
    assert checkpoint.read_bytes() == old_checkpoint


def test_public_model_and_control_validation_boundaries_preserve_artifacts(
    tmp_path: Path,
) -> None:
    """The complete public validation boundary must reject without artifact changes."""
    model = tmp_path / "validation.model"
    control = tmp_path / "validation.control"
    output = tmp_path / "preserved.ndjson"
    checkpoint = tmp_path / "preserved.state"
    write_cubic_model(model, x=0.0, a=1.0, bias=0.0)
    write_control(control, max_points=8)
    valid_model = model.read_text(encoding="utf-8")
    valid_control = control.read_text(encoding="utf-8")
    output.write_bytes(b"preserved output bytes")
    checkpoint.write_bytes(b"preserved checkpoint bytes")

    invalid_models = {
        "missing-key": valid_model.replace("bias=0\n", ""),
        "duplicate-key": valid_model + "a=1\n",
        "unknown-key": valid_model + "extra=1\n",
        "inline-comment": valid_model.replace("a=1\n", "a=1 # no inline comments\n"),
        "hex-float": valid_model.replace("a=1\n", "a=0x1p0\n"),
        "non-finite": valid_model.replace("a=1\n", "a=nan\n"),
        "wrong-vector-length": valid_model.replace("start_x=0\n", "start_x=0,0\n"),
        "zero-orientation": valid_model.replace("orientation=1, 0\n", "orientation=0,0\n"),
        "dimension-too-large": (
            "kind=bratu\ndimension=9\nstart_lambda=0\n"
            "start_x=0,0,0,0,0,0,0,0,0\n"
            "orientation=0,0,0,0,0,0,0,0,0,1\nscale=1\n"
        ),
        "wrong-kind-dimension": valid_model.replace("dimension=1\n", "dimension=2\n")
        .replace("start_x=0\n", "start_x=0,0\n")
        .replace("orientation=1, 0\n", "orientation=1,0,0\n"),
        "bad-start-residual": valid_model.replace("start_lambda=0\n", "start_lambda=0.1\n"),
        "singular-start-jacobian": valid_model.replace("a=1\n", "a=0\n"),
        "orthogonal-orientation": valid_model.replace(
            "orientation=1, 0\n", "orientation=1,-1\n"
        ),
        "bratu-dimension-one": (
            "kind=bratu\ndimension=1\nstart_lambda=0\nstart_x=0\n"
            "orientation=0,1\nscale=1\n"
        ),
        "bratu-nonpositive-scale": (
            "kind=bratu\ndimension=2\nstart_lambda=0\nstart_x=0,0\n"
            "orientation=0,0,1\nscale=0\n"
        ),
    }
    for label, contents in invalid_models.items():
        model.write_text(contents, encoding="utf-8")
        control.write_text(valid_control, encoding="utf-8")
        result = invoke("run", model, control, output, checkpoint)
        assert_contract_error(result, "model_invalid")
        assert output.read_bytes() == b"preserved output bytes", label
        assert checkpoint.read_bytes() == b"preserved checkpoint bytes", label

    def changed(key: str, value: str) -> str:
        return valid_control.replace(
            next(line for line in valid_control.splitlines(keepends=True) if line.startswith(f"{key}=")),
            f"{key}={value}\n",
        )

    invalid_controls = {
        "missing-key": valid_control.replace("max_points=8\n", ""),
        "duplicate-key": valid_control + "max_points=8\n",
        "unknown-key": valid_control + "extra=1\n",
        "non-finite": changed("initial_step", "inf"),
        "signed-integer": changed("fast_iterations", "+2"),
        "minimum-too-small": changed("min_step", "1e-9"),
        "minimum-after-initial": changed("min_step", "0.05"),
        "initial-after-maximum": changed("initial_step", "0.09"),
        "maximum-too-large": changed("max_step", "10.1"),
        "step-ratio-too-large": changed("min_step", "1e-8")
        .replace("initial_step=0.04\n", "initial_step=1\n")
        .replace("max_step=0.08\n", "max_step=10\n"),
        "grow-too-small": changed("grow_factor", "1"),
        "grow-too-large": changed("grow_factor", "4.01"),
        "shrink-too-small": changed("shrink_factor", "0.09"),
        "shrink-too-large": changed("shrink_factor", "0.81"),
        "fast-not-before-slow": changed("fast_iterations", "6"),
        "slow-after-maximum": changed("slow_iterations", "11"),
        "too-many-newton-iterations": changed("max_newton_iterations", "65"),
        "zero-residual-tolerance": changed("residual_tolerance", "0"),
        "zero-correction-tolerance": changed("correction_tolerance", "0"),
        "zero-fold-tolerance": changed("fold_tangent_tolerance", "0"),
        "too-few-points": changed("max_points", "1"),
        "too-many-points": changed("max_points", "513"),
    }
    model.write_text(valid_model, encoding="utf-8")
    for label, contents in invalid_controls.items():
        control.write_text(contents, encoding="utf-8")
        result = invoke("run", model, control, output, checkpoint)
        assert_contract_error(result, "control_invalid")
        assert output.read_bytes() == b"preserved output bytes", label
        assert checkpoint.read_bytes() == b"preserved checkpoint bytes", label


def test_error_precedence_is_command_then_model_then_control_then_state(
    tmp_path: Path,
) -> None:
    """Overlapping failures must report errors in the contract's precedence order."""
    model = tmp_path / "precedence.model"
    control = tmp_path / "precedence.control"
    output = tmp_path / "precedence.ndjson"
    checkpoint = tmp_path / "precedence.state"
    write_cubic_model(model, x=-0.8, a=1.2)
    write_control(control, max_points=7)
    valid_model = model.read_bytes()
    valid_control = control.read_bytes()
    output.write_bytes(b"preserved output")
    checkpoint.write_bytes(b"preserved state")
    old_output = output.read_bytes()
    old_checkpoint = checkpoint.read_bytes()

    # Command-shape validation wins even when a later pair of path strings conflicts.
    usage_first = execute(
        [
            BIN,
            "run",
            "--model",
            "relative.model",
            "--control",
            control,
            "--output",
            output,
            "--checkpoint",
            output,
        ]
    )
    assert_contract_error(usage_first, "usage")

    model.write_bytes(valid_model + b"unknown=1\n")
    control.write_bytes(valid_control + b"max_points=8\n")
    # Pairwise string conflict is checked before either malformed input file.
    path_first = invoke("run", model, control, output, output)
    assert_contract_error(path_first, "path_conflict")
    # With distinct paths, model content is checked before control content.
    model_first = invoke("resume", model, control, output, checkpoint)
    assert_contract_error(model_first, "model_invalid")
    model.write_bytes(valid_model)
    control_first = invoke("resume", model, control, output, checkpoint)
    assert_contract_error(control_first, "control_invalid")
    control.write_bytes(valid_control)
    assert output.read_bytes() == old_output
    assert checkpoint.read_bytes() == old_checkpoint

    checkpoint.unlink()
    state_last = invoke("resume", model, control, output, checkpoint)
    assert_contract_error(state_last, "state_missing")
    assert output.read_bytes() == old_output

    # A missing model is an operating-system input failure, not malformed content.
    missing_model = tmp_path / "missing.model"
    io_failure = invoke("run", missing_model, control, output, checkpoint)
    assert_io_error(io_failure)
    assert output.read_bytes() == old_output
    assert not checkpoint.exists()


def test_accept_limit_completion_boundary_and_invalid_limit_forms_preserve_artifacts(
    tmp_path: Path,
) -> None:
    """Acceptance limits must honor completion boundaries and strict decimal syntax."""
    model = tmp_path / "limit.model"
    control = tmp_path / "limit.control"
    output = tmp_path / "limit.ndjson"
    checkpoint = tmp_path / "limit.state"
    write_cubic_model(model, x=0.0, a=1.0, bias=0.3)
    write_control(control, initial_step=0.03, max_step=0.05, max_points=4)

    # Three newly accepted points plus run's initial point land exactly on max_points.
    completed = invoke("run", model, control, output, checkpoint, accept_limit=3)
    assert_success(completed)
    points, summary = validate_trace(
        output, model, control, expected_status="complete"
    )
    assert len(points) == 4
    assert summary["points"] == 4
    old_output = output.read_bytes()
    old_checkpoint = checkpoint.read_bytes()

    base: list[str | Path] = [
        BIN,
        "run",
        "--model",
        model,
        "--control",
        control,
        "--output",
        output,
        "--checkpoint",
        checkpoint,
    ]
    duplicate = execute(base + ["--accept-limit", "1", "--accept-limit", "2"])
    assert_contract_error(duplicate, "usage")
    zero = execute(base + ["--accept-limit", "0"])
    assert_contract_error(zero, "usage")
    assert output.read_bytes() == old_output
    assert checkpoint.read_bytes() == old_checkpoint


def test_complete_command_grammar_rejects_malformed_invocations_without_writes(
    tmp_path: Path,
) -> None:
    """Every malformed command shape must return usage without writing artifacts."""
    model = tmp_path / "grammar.model"
    control = tmp_path / "grammar.control"
    output = tmp_path / "grammar.ndjson"
    checkpoint = tmp_path / "grammar.state"
    write_cubic_model(model, x=-0.25, a=1.2)
    write_control(control, max_points=6)
    output.write_bytes(b"unchanged output")
    checkpoint.write_bytes(b"unchanged checkpoint")
    valid_options: list[str | Path] = [
        "--model",
        model,
        "--control",
        control,
        "--output",
        output,
        "--checkpoint",
        checkpoint,
    ]
    malformed: list[list[str | Path]] = [
        [],
        ["trace", *valid_options],
        ["run", *valid_options[:-2]],
        ["run", *valid_options, "--model", model],
        ["run", *valid_options, "--unknown", "1"],
        ["run", *valid_options, "dangling"],
        ["run", *valid_options, "--accept-limit", "-1"],
        ["run", *valid_options, "--accept-limit", "+1"],
        ["run", *valid_options, "--accept-limit", "1.0"],
        ["run", *valid_options, "--accept-limit", str(1 << 200)],
        [
            "run",
            "--model",
            model,
            "--control",
            "relative.control",
            "--output",
            output,
            "--checkpoint",
            checkpoint,
        ],
    ]
    for args in malformed:
        result = execute([BIN, *args])
        assert_contract_error(result, "usage")
        assert output.read_bytes() == b"unchanged output"
        assert checkpoint.read_bytes() == b"unchanged checkpoint"


def test_checkpoint_missing_corruption_and_raw_input_mismatch_preserve_bytes(
    tmp_path: Path,
) -> None:
    """Missing, malformed, and input-mismatched states must preserve supplied bytes."""
    model = tmp_path / "state.model"
    control = tmp_path / "state.control"
    output = tmp_path / "state.ndjson"
    checkpoint = tmp_path / "state.checkpoint"
    write_coupled_model(
        model,
        x0=-0.11,
        a=1.27,
        coupling=0.31,
        gain=0.52,
        bias1=-0.18,
        bias2=0.04,
    )
    write_control(control, max_points=10)
    valid_control = control.read_bytes()
    created = invoke("run", model, control, output, checkpoint, accept_limit=2)
    assert_success(created)
    validate_trace(output, model, control, expected_status="partial")
    valid_model = model.read_bytes()
    valid_checkpoint = checkpoint.read_bytes()
    valid_output = output.read_bytes()

    missing = tmp_path / "does-not-exist.state"
    missing_result = invoke("resume", model, control, output, missing)
    assert_contract_error(missing_result, "state_missing")
    assert output.read_bytes() == valid_output
    assert not missing.exists()

    checkpoint.write_bytes(b"not a foldpath checkpoint\x00\xff")
    corrupt_checkpoint = checkpoint.read_bytes()
    corrupt = invoke("resume", model, control, output, checkpoint)
    assert_contract_error(corrupt, "state_invalid")
    assert output.read_bytes() == valid_output
    assert checkpoint.read_bytes() == corrupt_checkpoint

    checkpoint.write_bytes(valid_checkpoint)
    model.write_bytes(valid_model + b"# Semantically harmless, but raw bytes changed.\n")
    changed_model = model.read_bytes()
    mismatch = invoke("resume", model, control, output, checkpoint)
    assert_contract_error(mismatch, "state_mismatch")
    assert model.read_bytes() == changed_model
    assert output.read_bytes() == valid_output
    assert checkpoint.read_bytes() == valid_checkpoint

    model.write_bytes(valid_model)
    control.write_bytes(valid_control + b"# Raw control bytes changed too.\n")
    changed_control = control.read_bytes()
    control_mismatch = invoke("resume", model, control, output, checkpoint)
    assert_contract_error(control_mismatch, "state_mismatch")
    assert control.read_bytes() == changed_control
    assert output.read_bytes() == valid_output
    assert checkpoint.read_bytes() == valid_checkpoint


def test_checkpoint_first_commit_recovers_after_output_rename_failure(
    tmp_path: Path,
) -> None:
    """A committed checkpoint must recover cleanly after the output commit fails."""
    model = tmp_path / "transaction.model"
    control = tmp_path / "transaction.control"
    checkpoint = tmp_path / "transaction.state"
    blocked_output = tmp_path / "output-is-a-directory"
    recovered_output = tmp_path / "recovered.ndjson"
    whole_output = tmp_path / "whole.ndjson"
    whole_checkpoint = tmp_path / "whole.state"
    write_coupled_model(
        model,
        x0=-0.24,
        a=1.44,
        coupling=0.22,
        gain=0.36,
        bias1=-0.09,
        bias2=0.025,
    )
    write_control(
        control,
        initial_step=0.029,
        max_step=0.071,
        grow_factor=1.19,
        max_points=13,
    )
    blocked_output.mkdir()

    failed = invoke(
        "run", model, control, blocked_output, checkpoint, accept_limit=3
    )
    assert_io_error(failed)
    assert blocked_output.is_dir()
    assert checkpoint.is_file(), "the checkpoint commit precedes output replacement"
    assert not list(tmp_path.glob("*.tmp.*")), "failed atomic writes must be cleaned"

    resumed = invoke(
        "resume", model, control, recovered_output, checkpoint, accept_limit=4
    )
    assert_success(resumed)
    recovered = validate_trace(
        recovered_output, model, control, expected_status="partial"
    )
    assert len(recovered[0]) == 8

    uninterrupted = invoke(
        "run", model, control, whole_output, whole_checkpoint, accept_limit=7
    )
    assert_success(uninterrupted)
    whole = validate_trace(whole_output, model, control, expected_status="partial")
    assert recovered == whole


def test_single_byte_checkpoint_corruption_is_never_accepted(tmp_path: Path) -> None:
    """Integrity protection must reject single-byte changes throughout a checkpoint."""
    model = tmp_path / "checksum.model"
    control = tmp_path / "checksum.control"
    output = tmp_path / "checksum.ndjson"
    checkpoint = tmp_path / "checksum.state"
    write_bratu_model(model, dimension=6, scale=0.82)
    write_control(control, initial_step=0.02, max_step=0.045, max_points=11)
    created = invoke("run", model, control, output, checkpoint, accept_limit=4)
    assert_success(created)
    original_output = output.read_bytes()
    original_state = checkpoint.read_bytes()
    assert len(original_state) > 32

    offsets = sorted(
        {
            0,
            1,
            7,
            8,
            15,
            len(original_state) // 3,
            len(original_state) // 2,
            len(original_state) - 9,
            len(original_state) - 1,
        }
    )
    for offset in offsets:
        damaged = bytearray(original_state)
        damaged[offset] ^= 0x5A
        checkpoint.write_bytes(damaged)
        result = invoke("resume", model, control, output, checkpoint)
        assert_contract_error(result, "state_invalid")
        assert output.read_bytes() == original_output
        assert checkpoint.read_bytes() == damaged
