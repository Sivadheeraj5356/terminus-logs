"""Verifier for the tape-engine replay task.

Strategy: build the agent's crate offline, drive its CLI to (re)produce the run
database and auxiliary runs, then check every correctness property against an
independent numpy reference engine (oracle.py) and via cross-run SQL joins. The
agent's own numbers are never trusted as ground truth; absolute values come from
the oracle, relationships come from live queries.
"""
import os
import sys
import glob
import shutil
import sqlite3
import subprocess
import math
import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import oracle

APP = "/app"
BIN = f"{APP}/target/release/engine"
DB = f"{APP}/out/runs.db"
SNAP = f"{APP}/out/snap"
WORK = "/tmp/tape_verifier"

TOL = 1e-7          # agent-vs-oracle (absorbs f64 libm/order noise)
EXACT = 1e-12       # same-engine cross-run comparisons


def run_bin(*args, expect_ok=True):
    r = subprocess.run([BIN, *args], capture_output=True, text=True)
    if expect_ok and r.returncode != 0:
        raise AssertionError(f"engine {args} failed ({r.returncode}): {r.stderr}")
    return r


def q(db, sql, params=()):
    con = sqlite3.connect(db)
    try:
        return con.execute(sql, params).fetchall()
    finally:
        con.close()


def find_snapshot(snap_dir, step):
    """Locate the snapshot resumable at `step`, tolerating any reasonable
    zero-padding (step_08.bin, step_8.bin, step_008.bin, ...). The spec pins
    step_%02d.bin, but we accept equivalents so a correct engine that pads
    differently still passes."""
    for name in (f"step_{step:02d}.bin", f"step_{step}.bin",
                 f"step_{step:03d}.bin", f"step_{step:04d}.bin"):
        p = os.path.join(snap_dir, name)
        if os.path.exists(p):
            return p
    for p in glob.glob(os.path.join(snap_dir, "step_*.bin")):
        digits = "".join(ch for ch in os.path.basename(p) if ch.isdigit())
        if digits and int(digits) == step:
            return p
    return None


@pytest.fixture(scope="session")
def built():
    r = subprocess.run(["cargo", "build", "--release", "--offline"],
                       cwd=APP, capture_output=True, text=True)
    assert r.returncode == 0, f"offline build failed:\n{r.stdout}\n{r.stderr}"
    assert os.path.exists(BIN), "engine binary not produced"
    return BIN


@pytest.fixture(scope="session")
def db(built):
    """Regenerate the canonical run database deterministically via the agent binary."""
    os.makedirs(f"{APP}/out", exist_ok=True)
    if os.path.exists(DB):
        os.remove(DB)
    shutil.rmtree(SNAP, ignore_errors=True)
    run_bin("--mode", "nocheckpoint")
    run_bin("--mode", "checkpoint")
    run_bin("--mode", "resume")
    return DB


@pytest.fixture(scope="session")
def orc():
    return oracle.Oracle(APP)


def steps_of(db, run_id):
    rows = q(db, "SELECT step, loss, grad_norm FROM steps WHERE run_id=? ORDER BY step", (run_id,))
    return {s: (ls, gn) for s, ls, gn in rows}


# The offline build is enforced by the `built` fixture (which asserts the crate
# compiles with `--offline`); it is a precondition every test below depends on, not
# a graded behavior of its own, so it has no standalone test.

# --------------------------------------------------------- T2/T3/T4/T17/T24 runs
def test_runs_present(db):
    rows = dict((rid, (mode, seed, rf)) for rid, mode, seed, rf
                in q(db, "SELECT run_id, mode, seed, resumed_from FROM runs"))
    assert "nocheckpoint" in rows and rows["nocheckpoint"][0] == "nocheckpoint"
    assert "checkpoint" in rows and rows["checkpoint"][0] == "checkpoint"
    assert "resume" in rows and rows["resume"][0] == "resume"
    assert rows["resume"][2] == "checkpoint", "resume must link resumed_from=checkpoint"
    assert rows["nocheckpoint"][2] is None and rows["checkpoint"][2] is None


def test_step_counts(db, orc):
    total = orc.total_steps()
    assert len(steps_of(db, "nocheckpoint")) == total
    assert len(steps_of(db, "checkpoint")) == total
    assert len(steps_of(db, "resume")) == total - orc.resume_step


# ------------------------------------------------- T5/T6/T7 remat invisibility
def test_checkpoint_equals_nocheckpoint_all_steps(db, orc):
    nc = steps_of(db, "nocheckpoint")
    ck = steps_of(db, "checkpoint")
    assert set(nc) == set(ck)
    for s in nc:
        assert abs(nc[s][0] - ck[s][0]) <= EXACT, f"loss diverges at step {s}"
        assert abs(nc[s][1] - ck[s][1]) <= EXACT, f"grad_norm diverges at step {s}"


def test_checkpoint_hash_equal_cross_mode(db):
    rows = q(db, """SELECT a.step FROM steps a JOIN steps b ON a.step=b.step
                    WHERE a.run_id='checkpoint' AND b.run_id='nocheckpoint'
                      AND a.checkpoint_hash <> b.checkpoint_hash""")
    assert rows == [], "full-state fingerprint must match between checkpoint and nocheckpoint"


# --------------------------------------------------- oracle absolute agreement
def test_all_steps_match_oracle(db, orc):
    expected = {s: (ls, gn) for s, ls, gn in orc.full_run(remat=True)}
    got = steps_of(db, "checkpoint")
    assert set(got) == set(expected)
    for s in expected:
        el, eg = expected[s]
        gl, gg = got[s]
        assert abs(gl - el) <= TOL + abs(el) * TOL, f"loss@{s}: {gl} vs oracle {el}"
        assert abs(gg - eg) <= TOL + abs(eg) * TOL, f"grad_norm@{s}: {gg} vs oracle {eg}"


def test_final_loss_matches_oracle(db, orc):
    expected = orc.full_run(remat=True)[-1]
    got = steps_of(db, "checkpoint")[expected[0]]
    assert abs(got[0] - expected[1]) <= TOL + abs(expected[1]) * TOL


# --------------------------------------------- T8 epoch boundary / ragged batch
def test_epoch_boundary_matches_oracle(db, orc):
    # first batch of epoch 1 is the first step whose correctness depends on the
    # ragged batch of epoch 0 having consumed the right number of draws.
    boundary = orc.bpe  # step index that begins epoch 1
    exp = {s: (ls, gn) for s, ls, gn in orc.full_run(remat=True)}[boundary]
    got = steps_of(db, "checkpoint")[boundary]
    assert abs(got[0] - exp[0]) <= TOL + abs(exp[0]) * TOL, "epoch-boundary loss desync (ragged batch)"
    assert abs(got[1] - exp[1]) <= TOL + abs(exp[1]) * TOL


# ----------------------------------------------------- T9/T23 unstable + clip
def test_layer3_clipped_not_altered(db, orc):
    """The recorded grad_norm must equal the oracle's *clipped* norm, not the
    unclipped one; and never NaN/Inf. This fails if layer 3 is 'fixed' (loss/norm
    drift) or left unclipped (norm too large)."""
    import numpy as np
    from oracle import Engine
    # recompute per-step pre-clip layer-3 norm and both clipped/unclipped globals
    eng = Engine(orc.cfg)
    rng = oracle.Rng(orc.seed)
    p = eng.init_params(rng)
    opt = {"m": {k: np.zeros_like(p[k]) for k in oracle.PARAM_ORDER},
           "v": {k: np.zeros_like(p[k]) for k in oracle.PARAM_ORDER}, "t": 0}
    cur = None
    clipped_steps = []
    got = steps_of(db, "checkpoint")
    for step in range(orc.total_steps()):
        bi = step % eng.bpe
        if bi == 0:
            cur = eng.epoch_perm(rng)
        s0 = bi * eng.b
        idx = cur[s0:min(s0 + eng.b, eng.n)]
        Xb, yb = orc.X[idx], orc.y[idx]
        f = eng.forward(p, Xb, rng, remat=True)
        loss, g = eng.backward(p, f, yb, rng, remat=True)
        preclip = math.sqrt(float((g["W3"] ** 2).sum() + (g["b3"] ** 2).sum()))
        eng.clip_layer3(g)
        clipped_norm = eng.global_norm(g)
        eng.adam(p, g, opt)
        assert math.isfinite(got[step][1]), f"grad_norm NaN/Inf at step {step}"
        assert abs(got[step][1] - clipped_norm) <= TOL + abs(clipped_norm) * TOL, \
            f"grad_norm@{step} should equal clipped norm"
        if preclip > oracle.CLIP_TAU:
            clipped_steps.append(step)
    assert len(clipped_steps) >= 1, "clip never engaged; the unstable layer must produce >tau grads"


# ------------------------------------------------- T11 Adam epsilon placement
def test_epsilon_outside_not_inside(db, orc):
    """Agent must match the outside-sqrt placement and NOT the inside variant."""
    import numpy as np
    # oracle with epsilon inside the sqrt
    def run_inside():
        eng = oracle.Engine(orc.cfg)
        rng = oracle.Rng(orc.seed)
        p = eng.init_params(rng)
        opt = {"m": {k: np.zeros_like(p[k]) for k in oracle.PARAM_ORDER},
               "v": {k: np.zeros_like(p[k]) for k in oracle.PARAM_ORDER}, "t": 0}
        cur = None
        out = {}
        for step in range(orc.total_steps()):
            bi = step % eng.bpe
            if bi == 0:
                cur = eng.epoch_perm(rng)
            s0 = bi * eng.b
            idx = cur[s0:min(s0 + eng.b, eng.n)]
            f = eng.forward(p, orc.X[idx], rng, remat=True)
            loss, g = eng.backward(p, f, orc.y[idx], rng, remat=True)
            eng.clip_layer3(g)
            out[step] = loss
            opt["t"] += 1
            t = opt["t"]
            for k in oracle.PARAM_ORDER:
                m = opt["m"][k]
                v = opt["v"][k]
                m[:] = oracle.BETA1 * m + (1 - oracle.BETA1) * g[k]
                v[:] = oracle.BETA2 * v + (1 - oracle.BETA2) * (g[k] * g[k])
                mhat = m / (1 - oracle.BETA1 ** t)
                vhat = v / (1 - oracle.BETA2 ** t)
                p[k] -= oracle.LR * mhat / np.sqrt(vhat + oracle.EPS)  # INSIDE
        return out
    inside = run_inside()
    outside = {s: ls for s, ls, gn in orc.full_run(remat=True)}
    got = steps_of(db, "checkpoint")
    # there must be a step where inside and outside differ meaningfully
    diff_step = next(s for s in outside if abs(inside[s] - outside[s]) > 1e-6)
    assert abs(got[diff_step][0] - outside[diff_step]) <= TOL + abs(outside[diff_step]) * TOL
    assert abs(got[diff_step][0] - inside[diff_step]) > 1e-6, "agent used epsilon INSIDE the sqrt"


# ------------------------------------------------------- T12/T26/T27 resume
def test_resume_matches_uninterrupted(db, orc):
    ck = steps_of(db, "checkpoint")
    rs = steps_of(db, "resume")
    assert rs, "resume produced no steps"
    for s in rs:
        assert abs(rs[s][0] - ck[s][0]) <= EXACT, f"resume loss diverges at step {s}"
        assert abs(rs[s][1] - ck[s][1]) <= EXACT, f"resume grad_norm diverges at step {s}"
    # and against the oracle's independent resume tail
    tail = {s: (ls, gn) for s, ls, gn in orc.resume_tail()}
    for s in rs:
        assert abs(rs[s][0] - tail[s][0]) <= TOL + abs(tail[s][0]) * TOL


def test_resume_state_fingerprint(db):
    rows = q(db, """SELECT c.step FROM steps c JOIN steps r ON c.step=r.step
                    WHERE c.run_id='checkpoint' AND r.run_id='resume'
                      AND c.checkpoint_hash <> r.checkpoint_hash""")
    assert rows == [], "resumed run's per-step state fingerprint must match uninterrupted run"


# ---------------------------------------------------- T15/T16 db structure
def test_integrity_and_foreign_keys(db):
    assert q(db, "PRAGMA integrity_check")[0][0] == "ok"
    assert q(db, "PRAGMA foreign_key_check") == []


def test_schema_columns(db):
    cols = {t: [r[1] for r in q(db, f"PRAGMA table_info({t})")]
            for t in ("runs", "steps", "checkpoints")}
    assert cols["runs"] == ["run_id", "mode", "seed", "resumed_from"]
    assert cols["steps"] == ["run_id", "step", "loss", "grad_norm", "checkpoint_hash"]
    assert cols["checkpoints"] == ["run_id", "step", "weights_hash",
                                   "optimizer_state_hash", "rng_state_hash"]


# ---------------------------------------------------------- T20 ragged manifest
def test_manifest_is_ragged(orc):
    assert orc.cfg["num_samples"] % orc.cfg["batch_size"] != 0


# ------------------------------------------------- T18/T19 rerun determinism
def _rerun(mode, tag):
    d = f"{WORK}/{tag}.db"
    sd = f"{WORK}/{tag}.snap"
    os.makedirs(WORK, exist_ok=True)
    for pth in (d,):
        if os.path.exists(pth):
            os.remove(pth)
    shutil.rmtree(sd, ignore_errors=True)
    if mode == "resume":
        # need a checkpoint chain first
        run_bin("--mode", "checkpoint", "--db", d, "--snap-dir", sd)
        run_bin("--mode", "resume", "--db", d, "--snap-dir", sd)
    else:
        run_bin("--mode", mode, "--db", d, "--snap-dir", sd)
    return d


def test_rerun_determinism_checkpoint(built):
    a = steps_of(_rerun("checkpoint", "ck_a"), "checkpoint")
    b = steps_of(_rerun("checkpoint", "ck_b"), "checkpoint")
    assert a == b, "same-seed checkpoint reruns must be identical"


def test_rerun_determinism_nocheckpoint(built):
    a = steps_of(_rerun("nocheckpoint", "nc_a"), "nocheckpoint")
    b = steps_of(_rerun("nocheckpoint", "nc_b"), "nocheckpoint")
    assert a == b, "same-seed nocheckpoint reruns must be identical"


# ------------------------------------------------ T25 held-out resume point
def test_heldout_resume_point(db, orc):
    """Resume from a second, mid-epoch snapshot (different from the shipped one)
    and check it still matches. Both fall mid-epoch, so the checkpoint must have
    captured the current epoch's batch order."""
    held = 2 * orc.bpe + 2  # step 10: middle of epoch 2, != shipped resume_step
    snap = find_snapshot(SNAP, held)
    assert snap, f"expected a snapshot resumable at step {held} under {SNAP}"
    d = f"{WORK}/held.db"
    if os.path.exists(d):
        os.remove(d)
    # need the run row to satisfy FK; reuse a fresh chain in this db
    shutil.rmtree(f"{WORK}/held.snap", ignore_errors=True)
    run_bin("--mode", "checkpoint", "--db", d, "--snap-dir", f"{WORK}/held.snap")
    held_snap = find_snapshot(f"{WORK}/held.snap", held)
    assert held_snap, f"checkpoint mode wrote no snapshot resumable at step {held}"
    run_bin("--mode", "resume", "--db", d, "--snap-dir", f"{WORK}/held.snap",
            "--snapshot", held_snap, "--run-id", "resume_held")
    got = steps_of(d, "resume_held")
    tail = {s: (ls, gn) for s, ls, gn in orc.resume_tail(held)}
    assert set(got) == set(tail)
    for s in got:
        assert abs(got[s][0] - tail[s][0]) <= TOL + abs(tail[s][0]) * TOL
        assert abs(got[s][1] - tail[s][1]) <= TOL + abs(tail[s][1]) * TOL


# --------------------------------------------------- T21 malformed checkpoint
def test_malformed_checkpoint_rejected(built, db):
    good = find_snapshot(SNAP, oracle.load_resume_step(f"{APP}/tests_fixtures/resume_point.toml"))
    assert good, "expected the resume-step snapshot to exist"
    os.makedirs(WORK, exist_ok=True)
    bad = f"{WORK}/truncated.bin"
    with open(good, "rb") as fh:
        data = fh.read()
    with open(bad, "wb") as fh:
        fh.write(data[: len(data) // 2])   # truncate
    d = f"{WORK}/bad.db"
    if os.path.exists(d):
        os.remove(d)
    run_bin("--mode", "checkpoint", "--db", d, "--snap-dir", f"{WORK}/bad.snap")  # seed a runs table
    r = run_bin("--mode", "resume", "--db", d, "--snapshot", bad,
                "--run-id", "resume_bad", expect_ok=False)
    assert r.returncode != 0, "resume from a truncated snapshot must exit nonzero"
    assert q(d, "SELECT COUNT(*) FROM steps WHERE run_id='resume_bad'")[0][0] == 0, \
        "a rejected resume must not write any step rows"


# ----------------------------------------- T13/T14 checkpoint-hash subset sensitivity
def _edit(src, dst, mutate):
    with open(src, "rb") as fh:
        b = bytearray(fh.read())
    mutate(b)
    with open(dst, "wb") as fh:
        fh.write(b)


def _hashes(path):
    """Parse the `hash` subcommand output. The spec pins `name=value` lines, but we
    also accept `name: value` and whitespace-separated `name value`, case-insensitive,
    so a correct engine with a slightly different format still passes."""
    r = run_bin("--mode", "hash", "--snapshot", path)
    keys = {"weights_hash", "optimizer_state_hash", "rng_state_hash", "full_hash"}
    out = {}
    for line in r.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        if "=" in line:
            k, v = line.split("=", 1)
        elif ":" in line:
            k, v = line.split(":", 1)
        else:
            parts = line.split()
            if len(parts) < 2:
                continue
            k, v = parts[0], parts[-1]
        k = k.strip().strip(":").lower()
        if k in keys:
            out[k] = v.strip()
    return out


def test_hash_subset_sensitivity(built, db, orc):
    rs = oracle.load_resume_step(f"{APP}/tests_fixtures/resume_point.toml")
    base = find_snapshot(SNAP, rs)
    assert base, "expected the resume-step snapshot to exist"
    os.makedirs(WORK, exist_ok=True)
    # snapshot layout:
    #   8 magic | 8 step | 8 adam_t | 8 rng | W weights | W m | W v | PERM | 8 checksum
    # where PERM = num_samples * 8 bytes (the current epoch's permutation).
    HEADER = 32
    perm_bytes = orc.cfg["num_samples"] * 8
    total = os.path.getsize(base)
    W = (total - HEADER - perm_bytes - 8) // 3
    base_h = _hashes(base)

    # (a) zero the optimizer region (m and v) -> opt hash changes, weights/rng do not
    zopt = f"{WORK}/zopt.bin"
    _edit(base, zopt, lambda b: b.__setitem__(slice(HEADER + W, HEADER + 3 * W),
                                              bytes(2 * W)))
    h = _hashes(zopt)
    assert h["weights_hash"] == base_h["weights_hash"]
    assert h["rng_state_hash"] == base_h["rng_state_hash"]
    assert h["optimizer_state_hash"] != base_h["optimizer_state_hash"], \
        "optimizer_state_hash must respond to optimizer state (T13)"
    assert h["full_hash"] != base_h["full_hash"]

    # (b) flip the rng_state bytes -> rng hash changes, weights/opt do not
    zrng = f"{WORK}/zrng.bin"
    def flip_rng(b):
        for i in range(24, 32):
            b[i] ^= 0xFF
    _edit(base, zrng, flip_rng)
    h = _hashes(zrng)
    assert h["weights_hash"] == base_h["weights_hash"]
    assert h["optimizer_state_hash"] == base_h["optimizer_state_hash"]
    assert h["rng_state_hash"] != base_h["rng_state_hash"], \
        "rng_state_hash must respond to PRNG state (T14)"
    assert h["full_hash"] != base_h["full_hash"]

    # (c) perturb one weight byte -> weights hash changes, others do not
    zw = f"{WORK}/zw.bin"
    _edit(base, zw, lambda b: b.__setitem__(HEADER, b[HEADER] ^ 0xFF))
    h = _hashes(zw)
    assert h["weights_hash"] != base_h["weights_hash"]
    assert h["optimizer_state_hash"] == base_h["optimizer_state_hash"]
    assert h["rng_state_hash"] == base_h["rng_state_hash"]


# ---------------------------------------------- checkpoints table sanity
def test_checkpoints_table_populated(db, orc):
    rows = q(db, "SELECT step, weights_hash, optimizer_state_hash, rng_state_hash "
                 "FROM checkpoints WHERE run_id='checkpoint' ORDER BY step")
    assert len(rows) >= 1
    # the three component hashes at a snapshot are distinct (not lazily filled equal)
    for step, wh, oh, rh in rows:
        assert len({wh, oh, rh}) == 3, f"component hashes collide at step {step}"
    # rng_state_hash varies across snapshots (state evolves)
    rhs = [r[3] for r in rows]
    assert len(set(rhs)) == len(rhs), "rng_state_hash must differ across snapshots"
