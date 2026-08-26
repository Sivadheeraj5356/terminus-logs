from __future__ import annotations

import hashlib
import os
import pathlib
import random
import subprocess

import pytest

from exact_model import parse, render

APP = pathlib.Path("/app")


@pytest.fixture(scope="session", autouse=True)
def build():
    expected = {
        "Cargo.toml": "34aab4e36252edbf27935ece85c0f043265f9d4e02d6fdc5a1ae21c7def1cae7",
        "Cargo.lock": "07aca771d26b8a0817cbef2316624bebdc6dbbba3aa970c9fd890aaa5c907c3a",
        "CUBIC_DIFFRACTION_PROTOCOL.md": "a987d799ecc5c2615010a3106fa8fe7a4db6409f3c896b645dfce7692fd72a5b",
        "src/main.rs": "a563172771846e17ab01bf93a12a3919e756eec853fe69c188a3fb2d05c73dfa",
        "src/model.rs": "ef181018d37ddc8ca5065ad825d46f037b6851079672b224346647c03b80cff8",
        "src/parser.rs": "68cb81d402c31b2d29d253734cef7b8508b557af03ab7b4ba3660152c35a4444",
        "src/render.rs": "f7200deb59706f2a8cb49c453eeec4c29a15ff449d92d689eec13fde43c4e2cf",
        "examples/sample.study": "fe1f2b2ac2f5c1e2430d97f8a303c3c31f149d9c0ea495615a899efb4fd8c338",
        "examples/sample.expected.json": "973da0b45ba1ec919ba4f7e965e62e8ec74f5bcdd7f80a965a02d77ea1852140",
    }
    for relative_path, digest in expected.items():
        actual = hashlib.sha256((APP / relative_path).read_bytes()).hexdigest()
        assert actual == digest, relative_path

    source_names = sorted(path.name for path in (APP / "src").glob("*.rs"))
    assert source_names == [
        "indexer.rs",
        "main.rs",
        "model.rs",
        "parser.rs",
        "render.rs",
    ]

    source = (APP / "src/indexer.rs").read_text()
    forbidden = [
        "std::fs",
        "std::process",
        "std::net",
        "Command::",
        "include!",
        "include_str!",
        "include_bytes!",
        "/tests",
        "/solution",
        "reward.txt",
        "unsafe {",
    ]
    assert not any(token in source for token in forbidden)

    environment = {**os.environ, "CARGO_NET_OFFLINE": "true"}
    subprocess.run(
        ["cargo", "build", "--offline", "--locked", "--release"],
        cwd=APP,
        check=True,
        env=environment,
    )
    (APP / "bin").mkdir(exist_ok=True)
    subprocess.run(
        [
            "cp",
            str(APP / "target/release/cubic-index"),
            str(APP / "bin/cubic-index"),
        ],
        check=True,
    )


def study(
    peaks_zero,
    peaks_one,
    *,
    phases="P I F",
    scale="10 11 1",
    shift="-1 1",
    limits="1 3 1",
    hmax=5,
    scan_range="0 1000",
):
    def block(name, peaks):
        records = [
            f"PEAK {peak_id} {q_value} {tolerance} {weight}"
            for peak_id, q_value, tolerance, weight in peaks
        ]
        return "\n".join([f"SCAN {name}", *records, "END"])

    return (
        "VERSION 1\n"
        f"HMAX {hmax}\n"
        f"SCAN_RANGE {scan_range}\n"
        f"SCALE {scale}\n"
        f"SHIFT {shift}\n"
        f"LIMITS {limits}\n"
        f"PHASES {phases}\n"
        f"{block('alpha', peaks_zero)}\n"
        f"{block('beta', peaks_one)}\n"
    )


def run_case(tmp_path, text, expect_ok=True):
    input_path = tmp_path / "study.txt"
    output_path = tmp_path / "result.json"
    input_path.write_text(text)
    process = subprocess.run(
        [
            str(APP / "bin/cubic-index"),
            "--study",
            str(input_path),
            "--output",
            str(output_path),
        ],
        capture_output=True,
    )
    if expect_ok:
        assert process.returncode == 0, process.stderr.decode()
        assert output_path.read_text() == render(parse(text))
    return process, output_path


def test_public_example(tmp_path):
    """The bundled study must reproduce the canonical public certificate."""
    text = (APP / "examples/sample.study").read_text()
    _, output_path = run_case(tmp_path, text)
    expected = (APP / "examples/sample.expected.json").read_text()
    assert output_path.read_text() == expected


def test_global_assignment_revises_nearest_peak(tmp_path):
    """The indexer must revise a locally nearest assignment to retain a later peak."""
    text = study(
        [("a", 19, 9, 9), ("b", 20, 0, 8)],
        [("c", 10, 0, 9), ("d", 20, 0, 8)],
        scale="10 10 0",
        shift="0 0",
        limits="0 4 2",
    )
    run_case(tmp_path, text)


def test_consensus_precedes_residual(tmp_path):
    """Consensus count must be compared before total residual."""
    text = study(
        [("a", 10, 0, 5), ("b", 31, 11, 5)],
        [("c", 10, 0, 5), ("d", 20, 10, 5)],
        scale="10 10 0",
        shift="0 0",
        limits="0 4 1",
    )
    run_case(tmp_path, text)


def test_phase_canonicalization_ignores_input_order(tmp_path):
    """Canonical phase ranking must not depend on declaration order."""
    text = study(
        [("a", 20, 0, 5), ("b", 40, 0, 5)],
        [("c", 20, 0, 5), ("d", 40, 0, 5)],
        phases="I P",
        scale="10 10 0",
        shift="0 0",
        limits="0 4 2",
    )
    run_case(tmp_path, text)


def test_optimal_count_includes_all_tied_assignments(tmp_path):
    """Every numerically tied full indexing plan must contribute to optimal_count."""
    text = study(
        [("a", 15, 5, 5)],
        [("b", 15, 5, 5)],
        scale="10 10 0",
        shift="0 0",
        limits="0 4 1",
        hmax=2,
    )
    _, output_path = run_case(tmp_path, text)
    output = output_path.read_text()
    assert '"optimal_count":' in output
    assert '"optimal_count":1' not in output


def test_missing_shell_limit_changes_assignment(tmp_path):
    """Missing-shell limits must be enforced on the final scan assignment."""
    text = study(
        [("a", 10, 0, 5), ("b", 40, 0, 5), ("c", 50, 0, 5)],
        [("d", 10, 0, 5), ("e", 40, 0, 5), ("f", 50, 0, 5)],
        scale="10 10 0",
        shift="0 0",
        limits="1 0 2",
        hmax=4,
    )
    run_case(tmp_path, text)


def test_drift_couples_calibrations(tmp_path):
    """The two scan calibrations must satisfy the shared scale-drift bound."""
    text = study(
        [("a", 10, 1, 5), ("b", 20, 1, 5)],
        [("c", 12, 1, 5), ("d", 24, 1, 5)],
        scale="10 12 1",
        shift="0 0",
        limits="0 3 2",
    )
    run_case(tmp_path, text)


def test_weighted_impurity_requires_global_choice(tmp_path):
    """Peak weights must be optimized globally rather than by nearest residual."""
    text = study(
        [("a", 10, 0, 1), ("b", 19, 9, 20), ("c", 20, 0, 15)],
        [("d", 10, 0, 1), ("e", 20, 0, 15)],
        scale="10 10 0",
        shift="0 0",
        limits="1 4 2",
    )
    run_case(tmp_path, text)


@pytest.mark.parametrize("seed", range(3))
def test_seeded_small_studies(tmp_path, seed):
    """Seeded studies must match the independent exact reference model."""
    generator = random.Random(seed)
    scale = 10
    peaks_zero = []
    peaks_one = []
    for index, shell in enumerate([1, 2, 3, 4]):
        peaks_zero.append(
            (
                f"a{index}",
                scale * shell + generator.choice([-1, 0, 1]),
                1,
                generator.randint(1, 9),
            )
        )
        peaks_one.append(
            (
                f"b{index}",
                scale * shell + generator.choice([-1, 0, 1]),
                1,
                generator.randint(1, 9),
            )
        )
    text = study(
        peaks_zero,
        peaks_one,
        scale="9 11 1",
        shift="-1 1",
        limits="1 4 2",
        hmax=5,
    )
    run_case(tmp_path, text)


def test_eight_peak_boundary(tmp_path):
    """The declared eight-peak boundary must be solved exactly."""
    shell_values = [1, 2, 3, 4, 5, 6, 8, 9]
    peaks_zero = [
        (f"a{index}", 10 * shell, 0, 10 - index)
        for index, shell in enumerate(shell_values)
    ]
    peaks_one = [
        (f"b{index}", 11 * shell, 0, 10 - index)
        for index, shell in enumerate(shell_values)
    ]
    text = study(
        peaks_zero,
        peaks_one,
        scale="10 11 1",
        shift="0 0",
        limits="0 8 6",
        hmax=6,
        scan_range="0 1000",
    )
    run_case(tmp_path, text)


def test_crlf_is_equivalent(tmp_path):
    """CRLF and LF studies must have identical semantics."""
    text = study(
        [("a", 10, 0, 5)],
        [("b", 10, 0, 5)],
        scale="10 10 0",
        shift="0 0",
        limits="0 1 1",
    ).replace("\n", "\r\n")
    run_case(tmp_path, text)


def test_validation_and_atomic_destination(tmp_path):
    """Malformed input must preserve an existing destination and report the first error."""
    input_path = tmp_path / "bad.txt"
    output_path = tmp_path / "out.json"
    output_path.write_text("keep")
    input_path.write_text("WHAT\n")
    process = subprocess.run(
        [
            str(APP / "bin/cubic-index"),
            "--study",
            str(input_path),
            "--output",
            str(output_path),
        ],
        capture_output=True,
    )
    assert process.returncode == 66
    assert process.stderr == b"study:1:BAD_ORDER\n"
    assert output_path.read_text() == "keep"


def test_unsafe_relative_path():
    """Relative paths must be rejected before reading input."""
    process = subprocess.run(
        [
            str(APP / "bin/cubic-index"),
            "--study",
            "relative",
            "--output",
            "/tmp/x",
        ],
        capture_output=True,
    )
    assert process.returncode == 65
    assert process.stderr == b"unsafe_path\n"
