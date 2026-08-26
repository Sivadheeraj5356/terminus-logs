"""Fixtures and sealed-grading setup for the anode-stringing verifier.

Anti-cheat, in order:
  * The sealed grading material (the primary and holdout true survival rates, cost tables, and
    thresholds) is read into memory once and unlinked from /tests, and the reference sources under
    /solution are unlinked too, BEFORE the agent's source is compiled or run, so a submitted program
    cannot open the answer key or fold in the reference sizer at grade time.
  * The binary is rebuilt from the agent's main.c with a FIXED verifier-owned `cc` command in an
    isolated tree; the agent's Makefile is never used, so a rewritten Makefile that copies a prebuilt
    program or writes a script is bypassed and the graded binary is provably compiled from the
    submitted C source.
  * The build and every run happen under an unprivileged account when the verifier holds the
    privilege to drop to one.
  * The SAME rebuilt binary is rerun against a disjoint holdout list (hz-01..), so a plan hardcoded
    to the shipped zn-01..zn-40 zones emits the wrong ids and cannot pass.

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
BIN = BUILD / "bin" / "stringer"
HOLDOUT_SRC = TESTS / "holdout"

_SEALED_NAMES = (
    "held_out_truth.json", "threshold.json", "costs.json",
    "holdout_truth.json", "holdout_threshold.json", "holdout_costs.json",
    "baseline.json",
)
_SEALED = {}  # name -> raw JSON text; each fixture parses a fresh copy
_SOLUTION_FILES = (SOLUTION / "main_oracle.c", SOLUTION / "solve.sh")


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
    # Drop the build+run to `nobody` when we hold the privilege; otherwise run as the current
    # (already unprivileged) user. HOME/TMPDIR point into the writable tree, while the rest of the
    # environment (PATH to the system cc) is inherited.
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
    """Rebuild in an isolated tree from the agent's main.c ONLY, using a fixed verifier-owned `cc`
    command. Depends on `sealed`, so the answer keys and reference sizer are gone before the compile.
    """
    if BUILD.exists():
        shutil.rmtree(BUILD, ignore_errors=True)
    (BUILD / "bin").mkdir(parents=True)
    (BUILD / "tmp").mkdir()

    src = ENV / "main.c"
    assert src.is_file() and not src.is_symlink(), "main.c must be a regular file, not a link"
    shutil.copy(src, BUILD / "main.c")
    _copy_regular_tree(ENV / "data", BUILD / "data")
    _copy_regular_tree(HOLDOUT_SRC, BUILD / "holdout")
    _chown_tree(BUILD)

    r = _run(["cc", "-O2", "-std=c11", "-o", str(BIN), str(BUILD / "main.c"), "-lm"], capture_err=True)
    assert r.returncode == 0, f"verifier cc build of main.c failed:\n{r.stderr}"
    assert BIN.exists(), "verifier cc did not produce bin/stringer"


def _run_binary(rel_dir):
    r = _run([str(BIN), rel_dir], timeout=120, capture_err=True)
    assert r.returncode == 0, f"stringer exited non-zero on {rel_dir}:\n{r.stderr}"
    return json.loads(r.stdout)["plan"]


@pytest.fixture(scope="session")
def _primary_rows(built):
    return _run_binary("data")


@pytest.fixture(scope="session")
def _holdout_rows(built):
    return _run_binary("holdout")


@pytest.fixture(scope="session")
def _survival_perturbed_rows(built):
    """Rerun on a copy of the shipped inputs with the SURVIVAL LOG perturbed and nothing else: every
    logged anode reads as having lasted (soil resistivity left untouched), so observed survival rises
    and a real sizer strings strictly fewer anodes while a fixed table does not move."""
    dst = BUILD / "survival_perturbed"
    if dst.exists():
        shutil.rmtree(dst)
    _copy_regular_tree(BUILD / "data", dst)

    log_lines = (dst / "survival_log.csv").read_text().splitlines()
    perturbed_log = [log_lines[0]] + [
        row.rsplit(",", 1)[0] + ",1" for row in log_lines[1:] if row.strip()
    ]
    (dst / "survival_log.csv").write_text("\n".join(perturbed_log) + "\n")
    _chown_tree(dst)
    return _run_binary("survival_perturbed")


@pytest.fixture(scope="session")
def _resistivity_perturbed_rows(built):
    """Rerun on a copy of the shipped inputs with SOIL RESISTIVITY perturbed and nothing else: every
    other zone's resistivity is lifted while the survival log is left untouched. Resistivity is the
    signal the instruction names for zones whose own retired-anode tally is too thin to trust, so a
    plan that reads it moves when it changes. A sizer that ignores the resistivity column -- e.g. a
    fixed multiple of the per-zone survival count -- emits an identical plan and is caught here. The
    bump is non-uniform (alternating zones) so it cannot be absorbed as a constant reference shift."""
    dst = BUILD / "resistivity_perturbed"
    if dst.exists():
        shutil.rmtree(dst)
    _copy_regular_tree(BUILD / "data", dst)

    zone_lines = (dst / "zones.csv").read_text().splitlines()
    perturbed_zones = [zone_lines[0]]
    body = [row for row in zone_lines[1:] if row.strip()]
    for i, row in enumerate(body):
        cols = row.split(",")
        if i % 2 == 0:
            cols[1] = f"{float(cols[1]) + 3.0:.4f}"
        perturbed_zones.append(",".join(cols))
    (dst / "zones.csv").write_text("\n".join(perturbed_zones) + "\n")
    _chown_tree(dst)
    return _run_binary("resistivity_perturbed")


def _plan_dict(rows):
    return {b["zone_id"]: b for b in copy.deepcopy(rows)}


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
def plan_survival_perturbed(_survival_perturbed_rows):
    return _plan_dict(_survival_perturbed_rows)


@pytest.fixture
def plan_resistivity_perturbed(_resistivity_perturbed_rows):
    return _plan_dict(_resistivity_perturbed_rows)


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


@pytest.fixture
def baseline():
    return json.loads(_SEALED["baseline.json"])
