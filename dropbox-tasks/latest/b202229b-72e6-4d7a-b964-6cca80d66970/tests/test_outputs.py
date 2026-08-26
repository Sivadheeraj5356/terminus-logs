"""Behavioural verification: exact per-query and per-checkpoint output compared against an independent replay."""

import contextlib
import csv
import json
import os
import shutil
import subprocess
import sys
import tempfile
from fractions import Fraction

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import reference  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
HIDDEN = os.path.join(HERE, "hidden")
PUBLIC = "/app/data"
RUN = "/app/run.sh"

BUNDLES = ["public"] + sorted(
    d for d in os.listdir(HIDDEN) if os.path.isdir(os.path.join(HIDDEN, d))
)


def bundle_path(name):
    return PUBLIC if name == "public" else os.path.join(HIDDEN, name)


def _ids(name, filename, key):
    with open(os.path.join(bundle_path(name), filename), newline="") as f:
        return [int(r[key]) for r in csv.DictReader(f)]


@contextlib.contextmanager
def oracle_out_of_reach():
    hidden = []
    src = os.path.join(HERE, "reference.py")
    cache = os.path.join(HERE, "__pycache__")
    stash = tempfile.mkdtemp(prefix="ref_")
    try:
        if os.path.exists(src):
            dst = os.path.join(stash, "reference.py")
            shutil.move(src, dst)
            hidden.append((dst, src))
        if os.path.isdir(cache):
            dst = os.path.join(stash, "__pycache__")
            shutil.move(cache, dst)
            hidden.append((dst, cache))
        yield
    finally:
        for frm, to in hidden:
            shutil.move(frm, to)
        shutil.rmtree(stash, ignore_errors=True)


def run_candidate(src):
    tmp = tempfile.mkdtemp(prefix="bundle_")
    try:
        dst = os.path.join(tmp, "data")
        shutil.copytree(src, dst)
        with oracle_out_of_reach():
            proc = subprocess.run(
                [RUN, dst], capture_output=True, text=True, timeout=900
            )
        assert proc.returncode == 0, (
            f"solver exited {proc.returncode}\nstderr:\n{proc.stderr[-3000:]}"
        )
        out = proc.stdout.strip()
        assert out, "solver produced no stdout"
        try:
            return json.loads(out)
        except json.JSONDecodeError as e:
            raise AssertionError(
                f"stdout is not valid JSON: {e}\nfirst 500 chars:\n{out[:500]}"
            )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


_cache = {}


def results(name):
    if name not in _cache:
        src = bundle_path(name)
        expected = reference.compute(src)
        got = run_candidate(src)
        _cache[name] = (expected, got)
    return _cache[name]


def _parse_frac(text):
    num, den = str(text).split("/")
    return Fraction(int(num), int(den))


def _got_predictions(got):
    return {int(q): _parse_frac(v) for q, v in got.get("predictions", [])}


def _got_checkpoints(got):
    return {int(c["id"]): c for c in got.get("checkpoints", [])}


PREDICTION_CASES = [
    (name, qid) for name in BUNDLES for qid in _ids(name, "queries.csv", "query_id")
]
CHECKPOINT_CASES = [
    (name, cid)
    for name in BUNDLES
    for cid in _ids(name, "checkpoints.csv", "checkpoint_id")
]


@pytest.mark.parametrize("name", BUNDLES)
def test_n_events(name):
    """Emitted n_events matches the replay."""
    exp, got = results(name)
    assert got.get("n_events") == exp["n_events"]


@pytest.mark.parametrize("name,qid", PREDICTION_CASES)
def test_prediction(name, qid):
    """Exact per-query predict-before-update output."""
    exp, got = results(name)
    g = _got_predictions(got)
    assert qid in g, f"missing prediction for query {qid} in '{name}'"
    assert g[qid] == exp["predictions"][qid], (
        f"prediction {qid} in '{name}': got {g[qid]} expected {exp['predictions'][qid]}"
    )


@pytest.mark.parametrize("name,cid", CHECKPOINT_CASES)
def test_checkpoint_active(name, cid):
    """Exact active-feature set at the checkpoint."""
    exp, got = results(name)
    g = _got_checkpoints(got)
    assert cid in g, f"missing checkpoint {cid} in '{name}'"
    assert [int(z) for z in g[cid]["active"]] == exp["checkpoints"][cid]["active"]


@pytest.mark.parametrize("name,cid", CHECKPOINT_CASES)
def test_checkpoint_gram(name, cid):
    """Exact retained coupled integer Gram (post-onset/retire dimension)."""
    exp, got = results(name)
    g = _got_checkpoints(got)
    assert cid in g, f"missing checkpoint {cid} in '{name}'"
    gg = [[int(a), int(b), int(v)] for a, b, v in g[cid]["gram"]]
    assert gg == [[a, b, int(v)] for a, b, v in exp["checkpoints"][cid]["gram"]]


@pytest.mark.parametrize("name,cid", CHECKPOINT_CASES)
def test_checkpoint_b(name, cid):
    """Exact retained integer right-hand side."""
    exp, got = results(name)
    g = _got_checkpoints(got)
    assert cid in g, f"missing checkpoint {cid} in '{name}'"
    gb = [[int(a), int(v)] for a, v in g[cid]["b"]]
    assert gb == [[a, int(v)] for a, v in exp["checkpoints"][cid]["b"]]


@pytest.mark.parametrize("name,cid", CHECKPOINT_CASES)
def test_checkpoint_weights(name, cid):
    """Exact rational weight vector solved from the retained coupled state."""
    exp, got = results(name)
    g = _got_checkpoints(got)
    assert cid in g, f"missing checkpoint {cid} in '{name}'"
    gw = {int(a): _parse_frac(v) for a, v in g[cid]["weights"]}
    ew = {a: v for a, v in exp["checkpoints"][cid]["weights"]}
    assert gw == ew, f"weights differ at checkpoint {cid} in '{name}'"


def test_relabelling_invariance():
    """Relabelling non-semantic feature ids leaves predictions invariant."""
    a = reference.compute(bundle_path("perm_base"))
    b = reference.compute(bundle_path("perm_relabel"))
    pa = [a["predictions"][q] for q in sorted(a["predictions"])]
    pb = [b["predictions"][q] for q in sorted(b["predictions"])]
    assert pa == pb and len(pa) > 0, (
        "predictions are not invariant under feature-id relabelling"
    )


def _replay_baseline(d, mode):
    cfg = reference.read_config(d)
    grace, lam, scale, delay = (
        cfg["grace_G"],
        cfg["lam"],
        cfg["scale"],
        cfg["label_delay"],
    )
    feat_ids, events = reference.read_events(d, scale)
    targets = reference.read_targets(d, scale)
    q_at = {}
    for qid, at in reference.read_pairs(d, "queries.csv", "query_id", "at_event"):
        q_at.setdefault(at, []).append(qid)

    active, active_set = [], set()
    gram, bvec, diag, absent, saved, pending = {}, {}, {}, {}, {}, {}
    predictions = {}
    delayed = mode in ("delayed_no_purge",)
    if mode == "impute0":
        for fid in feat_ids:
            active.append(fid)
            active_set.add(fid)
            bvec[fid] = diag[fid] = gram[(fid, fid)] = 0
            absent[fid] = 0

    def fold(items, y):
        for fi, xi in items:
            bvec[fi] = bvec.get(fi, 0) + y * xi
            diag[fi] = diag.get(fi, 0) + xi * xi
            for fj, xj in items:
                gram[(fi, fj)] = gram.get((fi, fj), 0) + xi * xj

    for eid, present in enumerate(events):
        if mode != "impute0":
            for fid in sorted(present):
                if fid not in active_set:
                    if mode == "resume" and fid in saved:
                        row, bf, dg = saved.pop(fid)
                        active.append(fid)
                        active_set.add(fid)
                        gram.update(row)
                        bvec[fid], diag[fid], absent[fid] = bf, dg, 0
                    else:
                        active.append(fid)
                        active_set.add(fid)
                        bvec[fid] = diag[fid] = gram[(fid, fid)] = 0
                        absent[fid] = 0
            for fid in list(active):
                if fid in present:
                    absent[fid] = 0
                else:
                    absent[fid] += 1
                    if absent[fid] > grace:
                        if mode == "resume":
                            saved[fid] = (
                                {k: v for k, v in gram.items() if fid in k},
                                bvec[fid],
                                diag[fid],
                            )
                        active.remove(fid)
                        active_set.discard(fid)
                        del bvec[fid], diag[fid], absent[fid]
                        for k in [kk for kk in gram if fid in kk]:
                            del gram[k]
        if mode == "impute0":
            x = {fid: present.get(fid, 0) for fid in active}
        else:
            x = {fid: present[fid] for fid in present if fid in active_set}
        if eid in q_at:
            if mode == "independent":
                yhat = sum(
                    (Fraction(bvec[f]) / (Fraction(diag[f]) + lam) * x[f] for f in x),
                    Fraction(0),
                )
            else:
                w = reference.solve(active, gram, bvec, lam)
                yhat = sum((w.get(f, Fraction(0)) * x[f] for f in x), Fraction(0))
            for qid in q_at[eid]:
                predictions[qid] = yhat
        if delayed:
            due = pending.pop(eid - delay, None)
            if due is not None:
                fold(list(due[0].items()), due[1])
            y = targets.get(eid)
            if y is not None:
                pending[eid] = (dict(x), y)
        else:
            y = targets.get(eid)
            if y is not None:
                fold(list(x.items()), y)
    return predictions


@pytest.mark.parametrize(
    "mode", ["impute0", "resume", "independent", "naive_immediate", "delayed_no_purge"]
)
def test_wrong_baseline_is_rejected(mode):
    """Each plausible wrong solver disagrees with the oracle somewhere, so the task is not vacuous."""
    disagreements = 0
    for name in BUNDLES:
        d = bundle_path(name)
        exp = reference.compute(d)["predictions"]
        base = _replay_baseline(d, mode)
        for q in exp:
            if base.get(q) != exp[q]:
                disagreements += 1
    assert disagreements > 0, f"the '{mode}' solver would pass; the task is vacuous"


def test_corpus_exercises_delayed_labels():
    """Delayed folding is load-bearing: folding at feature time diverges from the oracle."""
    diverged = 0
    for name in BUNDLES:
        d = bundle_path(name)
        exp = reference.compute(d)["predictions"]
        immediate = _replay_baseline(d, "naive_immediate")
        if any(immediate.get(q) != exp[q] for q in exp):
            diverged += 1
    assert diverged == len(BUNDLES), (
        f"only {diverged}/{len(BUNDLES)} bundles depend on the label delay"
    )


def test_corpus_exercises_retire_purge():
    """The retire-purge obligation changes graded output on multiple bundles."""
    fired = 0
    for name in BUNDLES:
        d = bundle_path(name)
        exp = reference.compute(d)["predictions"]
        nopurge = _replay_baseline(d, "delayed_no_purge")
        if any(nopurge.get(q) != exp[q] for q in exp):
            fired += 1
    assert fired >= 3, (
        f"retire-purge only alters {fired} bundles; obligation is barely exercised"
    )


def _read_config(d):
    return reference.read_config(d)


def test_corpus_exercises_retire_and_reinit():
    """The corpus actually retires features and reinitialises returning ones."""
    saw_retire = False
    saw_reinit = False
    for name in BUNDLES:
        d = bundle_path(name)
        cfg = _read_config(d)
        feat_ids, events = reference.read_events(d, cfg["scale"])
        active, absent = set(), {}
        ever_retired = set()
        for present in events:
            for fid in present:
                if fid not in active:
                    if fid in ever_retired:
                        saw_reinit = True
                    active.add(fid)
                    absent[fid] = 0
            for fid in list(active):
                if fid in present:
                    absent[fid] = 0
                else:
                    absent[fid] += 1
                    if absent[fid] > cfg["grace_G"]:
                        active.discard(fid)
                        ever_retired.add(fid)
                        saw_retire = True
    assert saw_retire, "no bundle ever retires a feature"
    assert saw_reinit, "no bundle ever reinitialises a returning feature"


def test_exact_arithmetic_is_load_bearing():
    """Retained weights have large rational denominators, so exact equality is required."""
    max_den = 1
    for name in BUNDLES:
        r = reference.compute(bundle_path(name))
        for snap in r["checkpoints"].values():
            for _, w in snap["weights"]:
                max_den = max(max_den, w.denominator)
    assert max_den > 10**12, (
        f"weight denominators are small ({max_den}); exactness is not exercised"
    )


def test_semantic_case_floor():
    """Report and enforce the executed semantic-case floor."""
    total = len(BUNDLES) + len(PREDICTION_CASES) + 4 * len(CHECKPOINT_CASES)
    print(
        f"\nexecuted semantic cases: {len(PREDICTION_CASES)} predictions + "
        f"{4 * len(CHECKPOINT_CASES)} checkpoint-property + {len(BUNDLES)} n_events = {total}"
    )
    assert total >= 60
