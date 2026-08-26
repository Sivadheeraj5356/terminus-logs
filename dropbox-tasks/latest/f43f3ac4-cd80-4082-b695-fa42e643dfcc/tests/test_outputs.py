"""Verifier for crossdate-sizing. Rebuilds the dater and scores its plan on a fresh season: each
site's anchor chance 1-(1-p_true)^n uses the sealed true rates, the floor binds on the weakest
site, committed cost against a sealed ceiling. /solution is emptied and the agent source compiles
and runs as an unprivileged account in an isolated tree (regular files only, symlinks refused).
"""

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
SOLUTION = Path("/solution")         # reference source, emptied before any agent build or run
BUILD = Path("/tmp/verifier_build")  # unprivileged scratch tree for the compile and run
BIN = BUILD / "bin" / "dater"


def _unpriv_ids():
    try:
        return pwd.getpwnam("nobody").pw_uid, grp.getgrnam("nogroup").gr_gid
    except KeyError:
        return 65534, 65534


BUILD_UID, BUILD_GID = _unpriv_ids()


def _run_unpriv(argv, timeout=300, merge=True):
    # Carry the toolchain env (RUSTUP_HOME/CARGO_HOME/PATH) but point HOME/TMPDIR at the tree.
    env = dict(os.environ, HOME=str(BUILD), TMPDIR=str(BUILD / "tmp"))
    return subprocess.run(
        argv, cwd=str(BUILD), text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT if merge else subprocess.PIPE, timeout=timeout,
        user=BUILD_UID, group=BUILD_GID, extra_groups=[], env=env,
    )


def _make(args, timeout=300):
    return _run_unpriv(["make", *args], timeout=timeout)


def _chown_tree(root):
    os.chown(root, BUILD_UID, BUILD_GID)
    for base, dirs, files in os.walk(root):
        for name in dirs + files:
            os.chown(os.path.join(base, name), BUILD_UID, BUILD_GID)


def _copy_regular_tree(src, dst):
    # Take regular files and real subdirectories only; a symlink is skipped, never followed.
    dst.mkdir(parents=True, exist_ok=True)
    for child in src.iterdir():
        if child.is_symlink():
            continue
        if child.is_dir():
            _copy_regular_tree(child, dst / child.name)
        elif child.is_file():
            shutil.copy(child, dst / child.name)


def _total_cores(entries):
    return {b["site_id"]: b["field_cores"] + b["contract_cores"] for b in entries}


@pytest.fixture(scope="session", autouse=True)
def sealed():
    """Load the sealed grading material into memory, then unlink it from /tests before any agent
    code has a chance to run."""
    data = {
        "truth": json.loads((TESTS / "held_out_truth.json").read_text()),
        "threshold": json.loads((TESTS / "threshold.json").read_text()),
        "costs": json.loads((TESTS / "costs.json").read_text()),
    }
    for name in ("held_out_truth.json", "threshold.json", "costs.json"):
        try:
            (TESTS / name).unlink()
        except OSError:
            pass
    return data


@pytest.fixture(scope="session", autouse=True)
def built(sealed):
    """Empty /solution, copy the agent's source (regular files only) into an unprivileged scratch
    tree, and compile it there."""
    if SOLUTION.exists():
        for child in SOLUTION.iterdir():
            try:
                if child.is_dir() and not child.is_symlink():
                    shutil.rmtree(child, ignore_errors=True)
                else:
                    child.unlink()
            except OSError:
                pass

    if BUILD.exists():
        shutil.rmtree(BUILD, ignore_errors=True)
    BUILD.mkdir(parents=True)
    (BUILD / "tmp").mkdir()

    for name in ("Makefile", "main.rs"):
        src = ENV / name
        assert src.is_file() and not src.is_symlink(), f"{name} must be a regular file, not a link"
        shutil.copy(src, BUILD / name)
    _copy_regular_tree(ENV / "data", BUILD / "data")
    _chown_tree(BUILD)

    _make(["clean"])
    r = _make([])
    assert r.returncode == 0, f"build failed:\n{r.stdout}"
    assert BIN.exists(), "make did not produce bin/dater"


@pytest.fixture(scope="session")
def plan(built, sealed):
    r = _run_unpriv([str(BIN), "data"], timeout=120, merge=False)
    assert r.returncode == 0, f"dater exited non-zero:\n{r.stderr}"
    entries = json.loads(r.stdout)["plan"]
    ids = [b["site_id"] for b in entries]
    # reject duplicate rows so a repeated site cannot last-wins-overwrite the lookup
    assert len(ids) == len(sealed["truth"]), f"expected {len(sealed['truth'])} plan rows, got {len(ids)}"
    assert len(set(ids)) == len(ids), "the plan contains duplicate site_id rows"
    return {b["site_id"]: b for b in entries}


def test_build_succeeds(built):
    """The agent's Rust code compiles."""
    assert BIN.exists()


def test_every_site_planned(plan, sealed):
    """The plan lists exactly the shipped sites, one entry apiece."""
    assert set(plan) == set(sealed["truth"]), "plan must cover exactly the shipped sites"


def test_cores_are_valid_nonneg_ints(plan):
    """Every field/contract core count is a non-negative integer."""
    for sid, b in plan.items():
        fc, cc = b["field_cores"], b["contract_cores"]
        assert isinstance(fc, int) and isinstance(cc, int), f"{sid}: core counts must be integers"
        assert fc >= 0 and cc >= 0, f"{sid}: core counts must be non-negative"


def test_field_budget_not_exceeded(plan, sealed):
    """Total field cores stay within the network-wide field core ration."""
    cap = sealed["threshold"]["field_core_budget"]
    used = sum(b["field_cores"] for b in plan.values())
    assert used <= cap, f"field cores {used} exceed the field core budget {cap}"


def test_anchor_floor_holds_on_season(plan, sealed):
    """On the held-out true rates the weakest site's anchor chance clears the floor (joint gate)."""
    truth = sealed["truth"]
    floor = sealed["threshold"]["anchor_floor"]
    worst = 1.0
    worst_site = None
    for sid, p in truth.items():
        n = plan[sid]["field_cores"] + plan[sid]["contract_cores"]
        anchor = 1.0 - (1.0 - p) ** n
        if anchor < worst:
            worst, worst_site = anchor, sid
    assert worst >= floor, f"anchor floor {floor} missed: worst site {worst_site} at {worst:.4f}"


def test_committed_cost_within_ceiling(plan, sealed):
    """Total committed cost stays within the sealed cost ceiling."""
    costs = sealed["costs"]
    ceiling = sealed["threshold"]["cost_ceiling"]
    cost = 0.0
    for sid, b in plan.items():
        cost += b["field_cores"] * costs[sid]["field_cost"]
        cost += b["contract_cores"] * costs[sid]["contract_cost"]
    assert cost <= ceiling, f"committed cost {cost:.2f} exceeds ceiling {ceiling:.2f}"


def test_plan_responds_to_input_data(built, plan):
    """The binary replans when inputs move (every core crossdated, sensitivity lifted), showing
    the counts are derived at run time, not baked in."""
    dst = BUILD / "perturbed"
    if dst.exists():
        shutil.rmtree(dst)
    _copy_regular_tree(BUILD / "data", dst)

    log_lines = (dst / "core_log.csv").read_text().splitlines()
    perturbed_log = [log_lines[0]] + [
        row.rsplit(",", 1)[0] + ",1" for row in log_lines[1:] if row.strip()
    ]
    (dst / "core_log.csv").write_text("\n".join(perturbed_log) + "\n")

    site_lines = (dst / "sites.csv").read_text().splitlines()
    perturbed_sites = [site_lines[0]]
    for row in site_lines[1:]:
        if not row.strip():
            continue
        cols = row.split(",")
        cols[1] = f"{float(cols[1]) + 10.0:.4f}"
        perturbed_sites.append(",".join(cols))
    (dst / "sites.csv").write_text("\n".join(perturbed_sites) + "\n")
    _chown_tree(dst)

    r = _run_unpriv([str(BIN), str(dst)], timeout=120, merge=False)
    assert r.returncode == 0, f"dater failed on perturbed inputs:\n{r.stderr}"
    moved = json.loads(r.stdout)["plan"]
    assert _total_cores(moved) != _total_cores(plan.values()), (
        "plan did not change when inputs changed; counts must be computed at run time"
    )
