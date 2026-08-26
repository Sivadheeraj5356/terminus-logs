"""Generate held-out labeling instances, run the candidate's rule-learning solver on each, and require its predictions to match the hidden test labels above the accuracy bar."""

import json
import os
import subprocess
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import reference  # noqa: E402

CRATE_DIR = os.environ.get("CRATE_DIR", "/app/environment")
BINARY = os.environ.get("SOLVER_BIN", os.path.join(CRATE_DIR, "target/release/solver"))
THRESHOLD = 0.99

# (name, seed, n_train, n_test). Each instance draws its own hidden rule parameters from its seed, so
# a solver must infer and fit the rule per instance rather than memorize one instance's answers.
INSTANCES = [
    ("public", 14, 6000, 3000),
    ("h1", 101, 6000, 3000),
    ("h2", 202, 5000, 3000),
    ("h3", 303, 7000, 2500),
    ("h4", 404, 6000, 3000),
    ("h5", 505, 8000, 2500),
    ("h6", 606, 6000, 2500),
]


@pytest.fixture(scope="module")
def built_binary():
    """Compile the candidate crate before exercising it."""
    env = dict(os.environ)
    env["PATH"] = "/usr/local/cargo/bin:" + env.get("PATH", "")
    proc = subprocess.run(
        ["cargo", "build", "--offline", "--release"],
        cwd=CRATE_DIR,
        capture_output=True,
        text=True,
        env=env,
        timeout=300,
    )
    assert proc.returncode == 0, f"cargo build failed:\n{proc.stderr}"
    assert os.path.exists(BINARY), f"binary not produced at {BINARY}"
    return BINARY


@pytest.fixture(scope="module")
def results(built_binary):
    out = {}
    for name, seed, ntr, nte in INSTANCES:
        d = os.path.join("/tmp", "inst_" + name)
        te_y = reference.write_instance(d, seed, ntr, nte)
        proc = subprocess.run(
            [built_binary, d], capture_output=True, text=True, timeout=120
        )
        assert proc.returncode == 0, (
            f"{name}: solver exited {proc.returncode}: {proc.stderr}"
        )
        pred = json.loads(proc.stdout)["predictions"]
        out[name] = (pred, te_y)
    return out


@pytest.mark.parametrize("name", [c[0] for c in INSTANCES])
def test_prediction_shape(results, name):
    """The solver returns one 0/1 prediction per test row."""
    pred, te_y = results[name]
    assert len(pred) == len(te_y)
    assert all(p in (0, 1) for p in pred)


@pytest.mark.parametrize("name", [c[0] for c in INSTANCES])
def test_accuracy_above_bar(results, name):
    """Predictions match the hidden test labels above the accuracy bar (only the true rule does)."""
    pred, te_y = results[name]
    acc = sum(a == b for a, b in zip(pred, te_y)) / len(te_y)
    assert acc >= THRESHOLD, f"{name}: accuracy {acc:.4f} below {THRESHOLD}"


def test_generalizes_across_instances(results):
    """The solver clears the bar on every instance, so it fits each instance's rule, not one memorized set."""
    for name, _seed, _ntr, _nte in INSTANCES:
        pred, te_y = results[name]
        acc = sum(a == b for a, b in zip(pred, te_y)) / len(te_y)
        assert acc >= THRESHOLD


def test_semantic_case_count(results):
    """Enforce the executed behavioral-case floor (>= 60 graded per-row predictions)."""
    total = sum(len(te_y) for _p, te_y in results.values())
    print(f"\nExecuted semantic cases: {total} graded test-row predictions (floor 60).")
    assert total >= 60
