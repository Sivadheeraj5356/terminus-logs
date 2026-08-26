#!/usr/bin/env python3
"""Agent-visible regressions for the foldpath contract's common failure modes."""

from __future__ import annotations

import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parent.parent
BIN = ROOT / "build" / "foldpath"
MODEL = ROOT / "examples" / "cubic.model"
CONTROL = ROOT / "examples" / "standard.control"


def invoke(
    command: str,
    output: Path,
    checkpoint: Path,
    limit: str | None = None,
) -> subprocess.CompletedProcess[str]:
    arguments = [
        str(BIN),
        command,
        "--model",
        str(MODEL),
        "--control",
        str(CONTROL),
        "--output",
        str(output),
        "--checkpoint",
        str(checkpoint),
    ]
    if limit is not None:
        arguments.extend(("--accept-limit", limit))
    return subprocess.run(arguments, text=True, capture_output=True, check=False)


def require_success(result: subprocess.CompletedProcess[str]) -> None:
    assert result.returncode == 0, (result.returncode, result.stdout, result.stderr)
    assert result.stdout == ""
    assert result.stderr == ""


def read_trace(path: Path) -> list[dict[str, object]]:
    raw = path.read_bytes()
    assert raw.endswith(b"\n") and not raw.endswith(b"\n\n")
    records = [json.loads(line) for line in raw.decode("utf-8").splitlines()]
    assert records and records[-1]["type"] == "summary"
    return records


def cubic_corrector_iterations(previous: dict[str, object], step: float) -> int:
    tangent = [float(value) for value in previous["tangent"]]  # type: ignore[index]
    old_x = float(previous["x"][0])  # type: ignore[index]
    old_lambda = float(previous["lambda"])
    predicted_x = old_x + step * tangent[0]
    predicted_lambda = old_lambda + step * tangent[1]
    x = predicted_x
    lam = predicted_lambda
    iterations = 0

    while True:
        residual = x * x * x - x + lam
        plane = tangent[0] * (x - predicted_x) + tangent[1] * (lam - predicted_lambda)
        if abs(residual) <= 1e-11 and abs(plane) <= 1e-11:
            return iterations
        assert iterations < 12
        jacobian = 3.0 * x * x - 1.0
        determinant = jacobian * tangent[1] - tangent[0]
        assert determinant != 0.0
        delta_x = ((-residual) * tangent[1] + plane) / determinant
        delta_lambda = (-jacobian * plane + tangent[0] * residual) / determinant
        x += delta_x
        lam += delta_lambda
        iterations += 1


def check_trace_geometry_and_newton(trace: list[dict[str, object]]) -> None:
    points = trace[:-1]
    assert len(points) == 5
    assert trace[-1]["status"] == "partial"
    for previous, point in zip(points, points[1:]):
        previous_x = [float(value) for value in previous["x"]]  # type: ignore[index]
        current_x = [float(value) for value in point["x"]]  # type: ignore[index]
        displacement = math.fsum(
            (right - left) ** 2 for left, right in zip(previous_x, current_x)
        )
        displacement += (
            float(point["lambda"]) - float(previous["lambda"])
        ) ** 2
        expected_arclength = float(previous["arclength"]) + math.sqrt(displacement)
        assert math.isclose(
            float(point["arclength"]), expected_arclength, rel_tol=2e-12, abs_tol=2e-12
        ), "arclength must use corrected-point Euclidean displacement"

        expected_iterations = cubic_corrector_iterations(
            previous, float(point["step_used"])
        )
        assert point["newton_iterations"] == expected_iterations, (
            "check convergence before solving and count only successful Newton solves",
            point["newton_iterations"],
            expected_iterations,
        )


def main() -> int:
    assert BIN.is_file(), f"missing {BIN}; run make clean all first"
    with tempfile.TemporaryDirectory(prefix="foldpath-contract-") as directory:
        scratch = Path(directory)

        output = scratch / "limited.ndjson"
        checkpoint = scratch / "limited.state"
        require_success(invoke("run", output, checkpoint, "4"))
        check_trace_geometry_and_newton(read_trace(output))

        old_output = output.read_bytes()
        old_checkpoint = checkpoint.read_bytes()
        malformed = invoke("run", output, checkpoint, "-1")
        assert malformed.returncode == 2
        assert malformed.stdout == ""
        assert malformed.stderr == '{"error":"usage"}\n'
        assert output.read_bytes() == old_output
        assert checkpoint.read_bytes() == old_checkpoint

        split_output = scratch / "split.ndjson"
        split_checkpoint = scratch / "split.state"
        whole_output = scratch / "whole.ndjson"
        whole_checkpoint = scratch / "whole.state"
        require_success(invoke("run", split_output, split_checkpoint, "3"))
        require_success(invoke("resume", split_output, split_checkpoint, "4"))
        require_success(invoke("resume", split_output, split_checkpoint))
        require_success(invoke("run", whole_output, whole_checkpoint))
        assert read_trace(split_output) == read_trace(whole_output)

        blocked_output = scratch / "output-is-a-directory"
        blocked_output.mkdir()
        recovery_checkpoint = scratch / "recovery.state"
        failed = invoke("run", blocked_output, recovery_checkpoint, "3")
        assert failed.returncode == 4
        assert failed.stdout == ""
        assert failed.stderr == '{"error":"io_error"}\n'
        assert blocked_output.is_dir()
        assert recovery_checkpoint.is_file()
        assert not list(scratch.glob("*.tmp.*"))

        recovered_output = scratch / "recovered.ndjson"
        comparison_output = scratch / "comparison.ndjson"
        comparison_checkpoint = scratch / "comparison.state"
        require_success(invoke("resume", recovered_output, recovery_checkpoint, "1"))
        require_success(invoke("run", comparison_output, comparison_checkpoint, "4"))
        assert read_trace(recovered_output) == read_trace(comparison_output)

    print("foldpath public contract checks passed")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as error:
        print(f"foldpath public contract check failed: {error}", file=sys.stderr)
        raise SystemExit(1)
