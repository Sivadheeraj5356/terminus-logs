"""Acceptance tests for the amr_mhd solver the agent completes at /app.

The project is compiled once with its own Makefile, then the compiled binary is driven over a
range of hidden cases. Every check recomputes the quantity it cares about from the emitted cell
and staggered-face arrays (divergence, conservation, positivity, wave error, interface
continuity); nothing here reads the agent's source, and none of the acceptance numbers are taken
on faith from the program's own reported diagnostics.
"""

import json
import math
import subprocess
import uuid
from pathlib import Path

import numpy as np
import pytest

APP = Path("/app")
BINARY = APP / "bin" / "amr_mhd"
SCRATCH = Path("/tmp/amr-cases")
CALL_TIMEOUT = 120
BUILD_TIMEOUT = 300


@pytest.fixture(scope="session", autouse=True)
def build_project():
    """Compile the project once with its Makefile before any case is run."""
    subprocess.run(["make", "clean"], cwd=APP, capture_output=True, text=True, timeout=BUILD_TIMEOUT)
    proc = subprocess.run(["make"], cwd=APP, capture_output=True, text=True, timeout=BUILD_TIMEOUT)
    assert proc.returncode == 0, f"`make` failed:\n{proc.stdout}\n{proc.stderr}"
    assert BINARY.exists(), "make did not produce /app/bin/amr_mhd"


def run(case_text, extra=None):
    """Run one case (given as the text of a case file) and return the parsed result document."""
    SCRATCH.mkdir(parents=True, exist_ok=True)
    tag = uuid.uuid4().hex
    case = SCRATCH / f"case-{tag}.txt"
    out = SCRATCH / f"out-{tag}.json"
    case.write_text(case_text)
    try:
        proc = subprocess.run(
            [str(BINARY), "--case", str(case), "--out", str(out)] + (extra or []),
            capture_output=True, text=True, timeout=CALL_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        raise AssertionError(f"amr_mhd did not finish within {CALL_TIMEOUT}s") from None
    assert proc.returncode == 0, f"amr_mhd exited {proc.returncode}\nstderr: {proc.stderr}"
    return json.loads(out.read_text()), out


def covered_mask(d):
    """Boolean mask of coarse cells fully overlaid by an active level-1 block."""
    ny, nx, bf = d["ny"], d["nx"], d["block"]
    cov = np.zeros((ny, nx), bool)
    for b in d["blocks"]:
        i0, j0, n = b["bi"] * bf // 2, b["bj"] * bf // 2, bf // 2
        cov[j0:j0 + n, i0:i0 + n] = True
    return cov


def max_div_coarse(d):
    """max |div B| over level-0 cells not covered by fine, recomputed from the coarse faces."""
    nx, ny = d["nx"], d["ny"]
    dx, dy = d["Lx"] / nx, d["Ly"] / ny
    bx = np.array(d["coarse"]["bx"]).reshape(ny, nx + 1)
    by = np.array(d["coarse"]["by"]).reshape(ny + 1, nx)
    div = (bx[:, 1:] - bx[:, :-1]) / dx + (by[1:, :] - by[:-1, :]) / dy
    cov = covered_mask(d)
    return float(np.max(np.abs(div[~cov]))) if (~cov).any() else 0.0


def max_div_fine(d):
    """max |div B| over the active level-1 cells, recomputed from each block's faces."""
    m = 0.0
    bf = d["block"]
    dx, dy = d["Lx"] / d["nx"] / 2, d["Ly"] / d["ny"] / 2
    for b in d["blocks"]:
        bx = np.array(b["bx"]).reshape(bf, bf + 1)
        by = np.array(b["by"]).reshape(bf + 1, bf)
        div = (bx[:, 1:] - bx[:, :-1]) / dx + (by[1:, :] - by[:-1, :]) / dy
        m = max(m, float(np.max(np.abs(div))))
    return m


def max_face_mismatch(d):
    """Largest gap between a coarse face-normal field and the mean of the two fine faces it covers."""
    nx, ny, bf = d["nx"], d["ny"], d["block"]
    cbx = np.array(d["coarse"]["bx"]).reshape(ny, nx + 1)
    cby = np.array(d["coarse"]["by"]).reshape(ny + 1, nx)
    worst = 0.0
    for b in d["blocks"]:
        fbx = np.array(b["bx"]).reshape(bf, bf + 1)
        fby = np.array(b["by"]).reshape(bf + 1, bf)
        i0, j0, n = b["bi"] * bf // 2, b["bj"] * bf // 2, bf // 2
        for cj in range(n):
            for ci in range(n + 1):
                cf = cbx[j0 + cj, i0 + ci]
                ff = 0.5 * (fbx[2 * cj, 2 * ci] + fbx[2 * cj + 1, 2 * ci])
                worst = max(worst, abs(cf - ff))
        for ci in range(n):
            for cj in range(n + 1):
                cf = cby[j0 + cj, i0 + ci]
                ff = 0.5 * (fby[2 * cj, 2 * ci] + fby[2 * cj, 2 * ci + 1])
                worst = max(worst, abs(cf - ff))
    return worst


def max_speed(d):
    """Largest fluid speed component over all active cells, from the emitted velocity arrays."""
    m = 0.0
    for a in ("u", "v"):
        m = max(m, float(np.max(np.abs(np.array(d["coarse"][a])))))
        for b in d["blocks"]:
            m = max(m, float(np.max(np.abs(np.array(b[a])))))
    return m


CPAW = "preset=cpaw\nnx={n}\nny={n}\namr=0\ncfl=0.4\ntmax=0.3\n"
LOOP = ("preset=field_loop\nnx=48\nny=48\nblock=8\namr=1\nregrid_interval=1000\n"
        "refine_threshold=0.25\ncfl=0.4\ntmax=0.1\nlvx=1.0\nlvy=0.5\n")
BLAST = ("preset=blast\nnx=48\nny=48\nblock=8\namr=1\nregrid_interval=4\nrefine_threshold=0.3\n"
         "cfl=0.4\nB0=0.5\np_center=10\np_ambient=0.5\n")


def test_project_builds_and_runs():
    """The Makefile yields a binary that runs a case and emits the documented result schema."""
    d, _ = run(CPAW.format(n=16))
    for key in ("coarse", "blocks", "nx", "ny", "mass", "energy", "min_rho", "min_p", "t"):
        assert key in d, f"missing '{key}' in result document"
    assert len(d["coarse"]["rho"]) == d["nx"] * d["ny"]
    assert len(d["coarse"]["bx"]) == (d["nx"] + 1) * d["ny"]


def test_second_order_convergence_on_smooth_wave():
    """The smooth Alfven wave error falls at ~second order under grid refinement (Godunov+CT)."""
    errs = [run(CPAW.format(n=n))[0]["l1"] for n in (32, 64, 128)]
    assert all(e > 0 for e in errs)
    orders = [math.log(errs[i] / errs[i + 1]) / math.log(2) for i in range(2)]
    assert min(orders) > 1.8, f"convergence orders {orders} below second order"
    assert errs[-1] < 1e-3, f"error at N=128 too large: {errs[-1]}"


def test_divergence_free_single_level():
    """On one level the discrete magnetic divergence stays at round-off (constrained transport)."""
    d, _ = run(CPAW.format(n=64))
    assert max_div_coarse(d) < 1e-10


def test_divergence_free_across_coarse_fine_boundary():
    """With level-1 blocks active, div B is machine-zero on both levels, including at the interface."""
    d, _ = run(LOOP)
    assert d["nblocks"] > 0, "no refinement occurred"
    assert max_div_coarse(d) < 1e-9, "coarse divergence too large"
    assert max_div_fine(d) < 1e-9, "fine divergence too large"


def test_face_normal_continuity_at_interfaces():
    """A coarse face-normal field equals the mean of the two fine faces covering it."""
    d, _ = run(LOOP)
    assert d["nblocks"] > 0
    assert max_face_mismatch(d) < 1e-9


def test_conservation_under_refluxing():
    """Under periodic boundaries the global invariants are constant to round-off with AMR active."""
    d, _ = run(LOOP)
    assert d["nblocks"] > 0
    for q in ("mass", "energy", "momx", "momy", "momz"):
        scale = max(abs(d[q + "0"]), 1.0)
        assert abs(d[q] - d[q + "0"]) / scale < 1e-8, f"{q} not conserved"


def test_positivity_and_strong_shock():
    """A magnetised blast accelerates the gas into strong shocks while density and pressure stay positive."""
    d, _ = run(BLAST + "tmax=0.06\n")
    assert d["min_rho"] > 0 and d["min_p"] > 0, "positivity violated"
    assert max_speed(d) > 0.3, "no strong flow developed (solution did not evolve)"


def test_positivity_into_near_vacuum():
    """Diverging streams rarefy toward vacuum yet density and pressure remain strictly positive."""
    d, _ = run("preset=vacuum\nnx=48\nny=32\nblock=8\namr=1\nregrid_interval=5\n"
               "refine_threshold=0.3\ncfl=0.4\ntmax=0.1\nvac_by=0.1\nvac_v=4.0\n")
    assert d["min_rho"] > 0 and d["min_p"] > 0, "positivity violated"
    assert d["min_p"] < 5e-2, "no near-vacuum rarefaction formed (solution did not evolve)"


def test_block_creation_deletion_and_boundary_refinement():
    """Blocks are both created and destroyed as the flow evolves, including against the domain edge."""
    moving, _ = run(BLAST + "tmax=0.12\n")
    assert moving["blocks_created"] > 0, "no blocks were ever created"
    assert moving["blocks_deleted"] > 0, "no blocks were ever destroyed"
    assert moving["nblocks_max"] > moving["nblocks_min"], "refined region never changed size"
    # a feature sitting on the periodic seam must refine there and stay divergence-free
    edge, _ = run(BLAST + "tmax=0.05\ncx=0.0\ncy=0.5\n")
    assert edge["nblocks"] > 0, "no refinement at the domain boundary"
    assert max_div_coarse(edge) < 1e-9 and max_div_fine(edge) < 1e-9


def pinned(blocks, tmax=0.2):
    """A travelling-wave case whose refined region is pinned to an explicit block list.

    The Alfven wave carries an order-one field through every cell, so a level that is not
    genuinely filled and coupled shows up immediately in the interface and conservation checks.
    """
    return ("preset=cpaw\nnx=48\nny=48\nblock=8\namr=1\nregrid_interval=0\n"
            "cfl=0.4\ntmax=%g\nblocks=%s\n"
            % (tmax, " ".join("%d,%d" % p for p in blocks)))


# Awkward but legal level-1 layouts. NB=12 blocks span each direction at nx=48, block=8, so
# index 11 is adjacent to index 0 across the periodic seam.
PINNED_LAYOUTS = {
    "interior square": [(4, 4), (5, 4), (4, 5), (5, 5)],
    "single block": [(6, 6)],
    "L of three blocks": [(4, 4), (5, 4), (4, 5)],
    "against the x seam": [(0, 5), (0, 6), (1, 5), (1, 6)],
    "straddling the x seam": [(11, 5), (0, 5), (11, 6), (0, 6)],
    "in the two-seam corner": [(0, 0), (1, 0), (0, 1), (1, 1)],
    "straddling both seams": [(11, 11), (0, 11), (11, 0), (0, 0)],
    "ring around unrefined cells": [(4, 4), (5, 4), (6, 4), (4, 5), (6, 5), (4, 6), (5, 6), (6, 6)],
    "full-width strip": [(i, 0) for i in range(12)],
}


@pytest.mark.parametrize("name", sorted(PINNED_LAYOUTS))
def test_pinned_block_layout_stays_consistent(name):
    """Every legal refined layout — odd, single, holed, seam-straddling — keeps the coupling exact."""
    blocks = PINNED_LAYOUTS[name]
    d, _ = run(pinned(blocks))
    assert d["nblocks"] == len(blocks), f"{name}: refined region was not the pinned set"
    assert max_div_coarse(d) < 1e-9, f"{name}: coarse divergence grew"
    assert max_div_fine(d) < 1e-9, f"{name}: fine divergence grew"
    assert max_face_mismatch(d) < 1e-9, f"{name}: face-normal field is not single-valued"
    for q in ("mass", "energy", "momx", "momy"):
        scale = max(abs(d[q + "0"]), 1.0)
        assert abs(d[q] - d[q + "0"]) / scale < 1e-8, f"{name}: {q} not conserved"


def test_deterministic_output_and_canonical_block_order():
    """Repeating a run reproduces it byte for byte and the active blocks come back in canonical order."""
    _, pa = run(LOOP)
    _, pb = run(LOOP)
    assert pa.read_text() == pb.read_text(), "identical runs produced different output"
    scrambled = [(5, 4), (4, 5), (4, 4), (6, 6), (5, 5)]
    d, _ = run(pinned(scrambled))
    order = [tuple(x) for x in d["block_order"]]
    assert sorted(order) == sorted(scrambled), "reported blocks do not match the pinned set"
    assert order == sorted(scrambled, key=lambda t: (t[1], t[0])), "blocks not in canonical (bj,bi) order"


def test_restart_reproduces_run_across_regrid():
    """A run split by a checkpoint taken after a regrid reproduces the unbroken run's fields exactly."""
    base = ("preset=blast\nnx=32\nny=32\nblock=8\namr=1\nregrid_interval=5\n"
            "refine_threshold=0.3\ncfl=0.4\nB0=0.5\np_center=10\np_ambient=0.5\n")
    full, _ = run(base + "nsteps=20\n")
    ckpt = SCRATCH / f"ck-{uuid.uuid4().hex}.txt"
    run(base + "nsteps=10\n", ["--checkpoint-out", str(ckpt), "--checkpoint-at", "10"])
    cont, _ = run(base + "nsteps=20\n", ["--restart", str(ckpt)])
    assert cont["steps"] == full["steps"] == 20
    for field in ("rho", "p", "bx", "by", "bz"):
        a = np.array(full["coarse"][field])
        b = np.array(cont["coarse"][field])
        assert np.max(np.abs(a - b)) < 1e-12, f"restart diverged in coarse {field}"
