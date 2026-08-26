"""Shared verifier scaffolding: seeds the graded evidence corpora and runs the engine.

The visible corpus at /app/data and the worked example are graded alongside FOUR corpora
seeded here, at verify time, from seeds the engine never sees.
"""
import os
import subprocess
import tempfile

import _ref

BIN = "/app/tariff/target/release/tariff"
HIDDEN_SEEDS = [7, 23, 53, 89]
_CACHE = {}


def corpora(n_hidden=None):
    """-> [(name, dir)] - the example, the visible corpus, then the seeded ones."""
    key = n_hidden or 0
    if key in _CACHE:
        return _CACHE[key]
    out = [("example", "/app/data/example"), ("visible", "/app/data")]
    root = tempfile.mkdtemp(prefix="corpora_")
    seeds = HIDDEN_SEEDS if n_hidden is None else HIDDEN_SEEDS[:n_hidden]
    for s in seeds:
        d = os.path.join(root, "seed_%d" % s)
        os.makedirs(d)
        _ref.seed_corpus(d, s)
        out.append(("seed_%d" % s, d))
    _CACHE[key] = out
    return out


def expect(data_dir, stage):
    k = (data_dir, stage)
    if k in _CACHE:
        return _CACHE[k]
    reg, segs, circs, disp = _ref.load_corpus(data_dir)
    res = _ref.audit(reg, segs, circs, disp, stage=stage)
    _CACHE[k] = (reg, res)
    return _CACHE[k]


def run(args, timeout=180):
    assert os.path.exists(BIN), "engine not built at %s" % BIN
    r = subprocess.run([BIN] + args, capture_output=True, text=True, timeout=timeout)
    assert r.returncode == 0, "tariff %s exited %d: %s" % (args[0], r.returncode,
                                                           r.stderr[-2000:])
    return r


def run_stage(data_dir, cmd):
    out = tempfile.mkdtemp(prefix="out_")
    run([cmd, "--data", data_dir, "--out", out])
    return out


def read(out_dir, name):
    p = os.path.join(out_dir, name)
    assert os.path.exists(p), "%s was not written" % name
    with open(p, "rb") as f:
        return f.read()
