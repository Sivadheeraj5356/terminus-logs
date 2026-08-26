import csv
import math
import os
import subprocess
from pathlib import Path

import pytest


ROOT = Path("/app/environment")
OUT = ROOT / "outputs"
FIXT = Path("/tests/fixtures")

NODES = 15
H = 1.0 / (NODES + 1)

# Reference values are independently recomputed and agree with a second,
# structurally unrelated construction to better than 1e-9 on every case.
REL_TOL = 1e-8
RESIDUAL_TOL = 1e-7


def read_contract(path):
    toks = Path(path).read_text().split()
    problem = toks[0]
    k = int(toks[1])
    m = int(toks[2])
    arclengths = [float(v) for v in toks[3 : 3 + m]]
    return problem, k, m, arclengths


def g(problem, v):
    return math.exp(v) if problem == "bratu" else v - v**3


def residual(problem, lam, u):
    worst = 0.0
    for i in range(NODES):
        um = 0.0 if i == 0 else u[i - 1]
        up = 0.0 if i == NODES - 1 else u[i + 1]
        r = (um - 2.0 * u[i] + up) / (H * H) + lam * g(problem, u[i])
        worst = max(worst, abs(r))
    return worst


def run_all(cases=None, data_dir=None):
    env = os.environ.copy()
    if cases is not None:
        env["CONT_CASES"] = str(cases)
    if data_dir is not None:
        env["CONT_DATA_DIR"] = str(data_dir)
    subprocess.run(
        ["bash", "scripts/run_all.sh"],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )


def read_rows(path):
    rows = []
    for line in Path(path).read_text().splitlines():
        parts = line.split()
        if not parts:
            continue
        rows.append([float(v) for v in parts[1:]])
    return rows


def load_cases(manifest):
    with open(manifest) as f:
        return [(row["name"], row["contract_path"]) for row in csv.DictReader(f)]


PUBLIC = load_cases(ROOT / "data" / "cases.csv")
HIDDEN = load_cases(FIXT / "hidden_cases.csv")


@pytest.fixture(scope="module")
def public_outputs():
    run_all()
    return {name: read_rows(OUT / f"{name}.txt") for name, _ in PUBLIC}


@pytest.fixture(scope="module")
def hidden_outputs():
    run_all(cases=FIXT / "hidden_cases.csv", data_dir=FIXT)
    return {name: read_rows(OUT / f"{name}.txt") for name, _ in HIDDEN}


def _grade(name, contract_path, base, rows):
    problem, _k, m, arclengths = read_contract(base / contract_path)
    expected = read_rows(FIXT / "expected" / f"{name}.txt")
    assert len(expected) == m, f"{name}: malformed reference fixture"
    assert len(rows) == m, f"{name}: expected {m} reported points, got {len(rows)}"

    for j, (got, want, s) in enumerate(zip(rows, expected, arclengths), 1):
        assert len(got) == NODES + 1, (
            f"{name}: point {j} has {len(got)} values, expected lambda plus {NODES} nodes"
        )
        assert all(math.isfinite(v) for v in got), f"{name}: point {j} is not finite"

        # Live invariant: the reported point must actually solve the system.
        res = residual(problem, got[0], got[1:])
        assert res <= RESIDUAL_TOL, (
            f"{name}: point {j} (s={s}) does not solve {problem}, residual={res:.3e}"
        )

        # Independent oracle: and it must be the right point of the right branch.
        for c, (a, b) in enumerate(zip(got, want)):
            tol = REL_TOL * max(1.0, abs(b))
            label = "lambda" if c == 0 else f"u_{c}"
            assert abs(a - b) <= tol, (
                f"{name}: point {j} (s={s}) {label} is {a!r}, reference {b!r}, "
                f"off by {abs(a - b):.3e} (tolerance {tol:.3e})"
            )


def test_case_lists_nonempty():
    """Both manifests list cases, so a missing manifest cannot vacuously pass grading."""
    assert len(PUBLIC) >= 24
    assert len(HIDDEN) >= 40


@pytest.mark.parametrize("name,path", PUBLIC)
def test_public_case(name, path, public_outputs):
    """Every reported point of each public case is the correct point of the named branch."""
    _grade(name, path, ROOT, public_outputs[name])


@pytest.mark.parametrize("name,path", HIDDEN)
def test_hidden_case(name, path, hidden_outputs):
    """Held-back contracts are graded the same way, so tuned or hardcoded output fails."""
    _grade(name, path, FIXT, hidden_outputs[name])


def test_public_outputs_present(public_outputs):
    """The build writes one full-length report per public case."""
    for name, path in PUBLIC:
        _problem, _k, m, _s = read_contract(ROOT / path)
        assert name in public_outputs and len(public_outputs[name]) == m


def test_outputs_directory_is_rebuilt():
    """A stale outputs directory is regenerated from source by the build script."""
    import shutil

    shutil.rmtree(OUT, ignore_errors=True)
    run_all()
    assert OUT.is_dir()
    for name, _ in PUBLIC:
        assert (OUT / f"{name}.txt").exists()


def test_results_are_deterministic(public_outputs):
    """Rebuilding and rerunning reproduces the reported points exactly."""
    before = {name: public_outputs[name] for name, _ in PUBLIC}
    run_all()
    for name, _ in PUBLIC:
        assert read_rows(OUT / f"{name}.txt") == before[name]


def test_interface_is_preserved():
    """The declared trace_branch interface in the public header stays unchanged."""
    header = (ROOT / "include" / "continuation.hpp").read_text()
    normalized = " ".join(header.split())
    expected = (
        "std::vector<CurvePoint> trace_branch(const std::string &problem, int k, "
        "const std::vector<double> &arclengths);"
    )
    assert expected in normalized, "trace_branch declaration was altered"
