"""Fixtures and sealed-grading setup for the wick-proving verifier.

Anti-cheat, in order:
  * The sealed grading material (the primary and holdout true rates, the cost tables, and the
    thresholds) is read into memory once and unlinked from /tests, and the oracle sources under
    /solution are unlinked too, all BEFORE the agent's source is compiled or run, so a submitted
    program can neither open the answer key nor pull in the reference planner at grade time.
  * The binary is rebuilt from the agent's main.rs with a FIXED verifier-owned `rustc` call in an
    isolated tree; the agent's Makefile never runs, so a rewritten Makefile that copies in a prebuilt
    program or drops a script is bypassed and the graded binary is provably compiled from the
    submitted Rust.
  * The compile and every run happen under an unprivileged account whenever the verifier holds the
    privilege to drop to one.
  * That same rebuilt binary is run again on a disjoint holdout board (ch-01..), so a plan hardcoded
    to the shipped cd-01..cd-40 designs prints the wrong ids and cannot pass.

No shared mutable state: the sealed files are kept as raw text and each fixture parses its own fresh
object, and plan dicts are deep-copied per test.
"""

import copy
import grp
import json
import os
import pwd
import shutil
import subprocess
from pathlib import Path

import pytest

ENV = Path("/app/environment")
TESTS = Path(__file__).resolve().parent
SOLUTION = Path("/solution")
BUILD = Path("/tmp/verifier_build")
BIN = BUILD / "bin" / "chandler"
HOLDOUT_SRC = TESTS / "holdout"

_SEALED_NAMES = (
    "held_out_truth.json", "threshold.json", "costs.json",
    "holdout_truth.json", "holdout_threshold.json", "holdout_costs.json",
)
_SEALED = {}  # name -> raw JSON text; each fixture parses a fresh copy
_SOLUTION_FILES = (SOLUTION / "main_oracle.rs", SOLUTION / "solve.sh")


def _unpriv_ids():
    try:
        return pwd.getpwnam("nobody").pw_uid, grp.getgrnam("nogroup").gr_gid
    except KeyError:
        return 65534, 65534


BUILD_UID, BUILD_GID = _unpriv_ids()
IS_ROOT = os.geteuid() == 0


def _seal_grading_material():
    if _SEALED:
        return
    for name in _SEALED_NAMES:
        _SEALED[name] = (TESTS / name).read_text()
    for name in _SEALED_NAMES:
        try:
            (TESTS / name).unlink()
        except OSError:
            pass
    for p in _SOLUTION_FILES:
        try:
            p.unlink()
        except OSError:
            pass


def _copy_regular_tree(src, dst):
    """Copy regular files and real subdirectories only; skip any symlink."""
    dst.mkdir(parents=True, exist_ok=True)
    for child in src.iterdir():
        if child.is_symlink():
            continue
        if child.is_dir():
            _copy_regular_tree(child, dst / child.name)
        elif child.is_file():
            shutil.copy(child, dst / child.name)


def _chown_tree(root):
    if not IS_ROOT:
        return
    os.chown(root, BUILD_UID, BUILD_GID)
    for base, dirs, files in os.walk(root):
        for name in dirs + files:
            os.chown(os.path.join(base, name), BUILD_UID, BUILD_GID)


def _run(argv, timeout=300, capture_err=False):
    # Drop the build and run to `nobody` when we hold the privilege; otherwise stay as the current
    # (already unprivileged) user. HOME/TMPDIR point into the writable tree while the rest of the
    # toolchain env (RUSTUP_HOME/CARGO_HOME/PATH) is inherited so the rustup rustc proxy resolves.
    env = dict(os.environ, HOME=str(BUILD), TMPDIR=str(BUILD / "tmp"))
    kw = dict(
        cwd=str(BUILD), text=True, stdout=subprocess.PIPE, timeout=timeout, env=env,
        stderr=subprocess.PIPE if capture_err else subprocess.STDOUT,
    )
    if IS_ROOT:
        kw.update(user=BUILD_UID, group=BUILD_GID, extra_groups=[])
    return subprocess.run(argv, **kw)


@pytest.fixture(scope="session", autouse=True)
def sealed():
    _seal_grading_material()


@pytest.fixture(scope="session", autouse=True)
def built(sealed):
    """Rebuild in an isolated tree from the agent's main.rs ONLY, under a fixed verifier-owned rustc
    call. Depends on `sealed`, so the answer keys and the oracle are gone before the compile runs.
    """
    if BUILD.exists():
        shutil.rmtree(BUILD, ignore_errors=True)
    (BUILD / "bin").mkdir(parents=True)
    (BUILD / "tmp").mkdir()

    src = ENV / "main.rs"
    assert src.is_file() and not src.is_symlink(), "main.rs must be a regular file, not a link"
    shutil.copy(src, BUILD / "main.rs")
    _copy_regular_tree(ENV / "data", BUILD / "data")
    _copy_regular_tree(HOLDOUT_SRC, BUILD / "holdout")
    _chown_tree(BUILD)

    r = _run(["rustc", "-O", "-o", str(BIN), str(BUILD / "main.rs")], capture_err=True)
    assert r.returncode == 0, f"verifier rustc build of main.rs failed:\n{r.stderr}"
    assert BIN.exists(), "verifier rustc did not produce bin/chandler"


def _run_binary(rel_dir):
    r = _run([str(BIN), rel_dir], timeout=120, capture_err=True)
    assert r.returncode == 0, f"chandler exited non-zero on {rel_dir}:\n{r.stderr}"
    return json.loads(r.stdout)["plan"]


@pytest.fixture(scope="session")
def _primary_rows(built):
    return _run_binary("data")


@pytest.fixture(scope="session")
def _holdout_rows(built):
    return _run_binary("holdout")


@pytest.fixture(scope="session")
def _perturbed_rows(built):
    """Rerun on a perturbed copy of the shipped inputs: every logged candle reads clean and every
    blend_grade is lifted, so the observed rates rise and a real planner commits strictly fewer
    candles while a fixed table does not move."""
    dst = BUILD / "perturbed"
    if dst.exists():
        shutil.rmtree(dst)
    _copy_regular_tree(BUILD / "data", dst)

    log_lines = (dst / "burn_log.csv").read_text().splitlines()
    perturbed_log = [log_lines[0]] + [
        row.rsplit(",", 1)[0] + ",1" for row in log_lines[1:] if row.strip()
    ]
    (dst / "burn_log.csv").write_text("\n".join(perturbed_log) + "\n")

    design_lines = (dst / "designs.csv").read_text().splitlines()
    perturbed_designs = [design_lines[0]]
    for row in design_lines[1:]:
        if not row.strip():
            continue
        cols = row.split(",")
        cols[1] = f"{float(cols[1]) + 10.0:.4f}"
        perturbed_designs.append(",".join(cols))
    (dst / "designs.csv").write_text("\n".join(perturbed_designs) + "\n")
    _chown_tree(dst)
    return _run_binary("perturbed")


def _plan_dict(rows):
    return {b["design_id"]: b for b in copy.deepcopy(rows)}


@pytest.fixture
def bin_path(built):
    return BIN


@pytest.fixture
def plan_rows(_primary_rows):
    return copy.deepcopy(_primary_rows)


@pytest.fixture
def plan(_primary_rows):
    return _plan_dict(_primary_rows)


@pytest.fixture
def plan_perturbed(_perturbed_rows):
    return _plan_dict(_perturbed_rows)


@pytest.fixture
def holdout_plan(_holdout_rows):
    return _plan_dict(_holdout_rows)


@pytest.fixture
def truth():
    return json.loads(_SEALED["held_out_truth.json"])


@pytest.fixture
def threshold():
    return json.loads(_SEALED["threshold.json"])


@pytest.fixture
def costs():
    return json.loads(_SEALED["costs.json"])


@pytest.fixture
def holdout_truth():
    return json.loads(_SEALED["holdout_truth.json"])


@pytest.fixture
def holdout_threshold():
    return json.loads(_SEALED["holdout_threshold.json"])


@pytest.fixture
def holdout_costs():
    return json.loads(_SEALED["holdout_costs.json"])
