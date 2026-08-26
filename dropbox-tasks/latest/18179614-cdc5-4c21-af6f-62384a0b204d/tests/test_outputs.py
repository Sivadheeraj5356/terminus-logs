#!/usr/bin/env python3
"""Verifier for logknopp-mass-transfer-lab."""
from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path("/app/environment")
BUILD = ROOT / "build"
OUTPUT = Path("/app/output")
VAR = Path("/app/var/massxfer")
REPORT = OUTPUT / "mass_report.json"
TRACE = OUTPUT / "plan_trace.csv"
CACHE = VAR / "dual_cache.json"
LEDGER = VAR / "run_ledger.json"
INST_VAULT = Path("/var/lib/verifier/instances-vault")
TOL = 1e-7


def _logsumexp(xs: list[float]) -> float:
    m = max(xs)
    if not math.isfinite(m):
        return m
    return m + math.log(sum(math.exp(x - m) for x in xs))


def _sinkhorn_log(
    cost: list[list[float]],
    a: list[float],
    b: list[float],
    eps: float,
    max_iters: int = 8000,
    tol: float = 1e-9,
    warm_f: list[float] | None = None,
    warm_g: list[float] | None = None,
) -> tuple[list[list[float]], float, list[float], list[float]]:
    n, m = len(a), len(b)
    log_k = [[-cost[i][j] / eps for j in range(m)] for i in range(n)]
    f = list(warm_f) if warm_f is not None else [0.0] * n
    g = list(warm_g) if warm_g is not None else [0.0] * m
    for _ in range(max_iters):
        for i in range(n):
            f[i] = math.log(a[i]) - _logsumexp([log_k[i][j] + g[j] for j in range(m)])
        for j in range(m):
            g[j] = math.log(b[j]) - _logsumexp([log_k[i][j] + f[i] for i in range(n)])
        resid = 0.0
        for i in range(n):
            row = sum(math.exp(f[i] + log_k[i][j] + g[j]) for j in range(m))
            resid = max(resid, abs(row - a[i]))
        for j in range(m):
            col = sum(math.exp(f[i] + log_k[i][j] + g[j]) for i in range(n))
            resid = max(resid, abs(col - b[j]))
        if resid <= tol:
            break
    plan = [
        [math.exp(f[i] + log_k[i][j] + g[j]) for j in range(m)] for i in range(n)
    ]
    w = sum(plan[i][j] * cost[i][j] for i in range(n) for j in range(m))
    return plan, w, f, g


def _solve_instance(inst: dict) -> dict:
    a = [float(x) for x in inst["supply"]]
    b = [float(x) for x in inst["demand"]]
    cost = [[float(x) for x in row] for row in inst["cost"]]
    n, m = len(a), len(b)
    if (
        n == 0
        or m == 0
        or len(cost) != n
        or any(len(r) != m for r in cost)
        or float(inst["epsilon"]) <= 0
        or any(v <= 0 for v in a)
        or any(v <= 0 for v in b)
        or abs(sum(a) - sum(b)) > 1e-9
    ):
        return {
            "accepted": False,
            "plan": [],
            "wasserstein": 0.0,
            "plan_digest_hex": "",
        }
    target = float(inst["epsilon"])
    anneal = inst.get("anneal")
    f = g = None
    plan: list[list[float]] = []
    w = 0.0
    if anneal:
        stages = [
            float(anneal["start_epsilon"]) * (float(anneal["factor"]) ** t)
            for t in range(int(anneal["stages"]))
        ]
        if stages:
            if stages[-1] > target + 1e-18:
                stages.append(target)
            elif abs(stages[-1] - target) > 1e-18:
                stages[-1] = target
        else:
            stages = [target]
        for eps in stages:
            plan, w, f, g = _sinkhorn_log(cost, a, b, eps, warm_f=f, warm_g=g)
    else:
        plan, w, f, g = _sinkhorn_log(cost, a, b, target)
    parts = [f"{i},{j}:{plan[i][j]:.17e}" for i in range(n) for j in range(m)]
    dig = hashlib.sha256(";".join(parts).encode()).hexdigest()
    return {
        "accepted": True,
        "plan": plan,
        "wasserstein": w,
        "plan_digest_hex": dig,
        "rows": n,
        "cols": m,
    }


def _eval_file(path: Path) -> dict:
    raw = path.read_bytes()
    inst = json.loads(raw.decode())
    out = _solve_instance(inst)
    out["instance_digest_hex"] = hashlib.sha256(raw).hexdigest()
    out["instance_id"] = inst.get("instance_id", "")
    return out


def _rebuild() -> None:
    subprocess.run(["bash", str(ROOT / "scripts/rebuild.sh")], check=True)


def _run(reset: bool = True, env: dict | None = None) -> None:
    merged = os.environ.copy()
    if env:
        merged.update(env)
    args = ["--reset"] if reset else []
    subprocess.run([str(BUILD / "otctl-run"), *args], check=True, env=merged)


def _probe(label: str) -> str:
    return subprocess.check_output([str(BUILD / "otctl-probe"), label], text=True).strip()


def _probe_w(label: str) -> str:
    return subprocess.check_output(
        [str(BUILD / "otctl-probe"), "wasserstein", label], text=True
    ).strip()


def _audit() -> str:
    return subprocess.check_output([str(BUILD / "otctl-audit")], text=True).strip()


def _inspect(label: str) -> str:
    return subprocess.check_output(
        [str(BUILD / "otctl-inspect"), label], text=True
    ).strip()


def _profile(rep: dict, label: str) -> dict:
    for p in rep["profiles"]:
        if p["label"] == label:
            return p
    raise KeyError(label)


def _restore_vault() -> None:
    dst = ROOT / "data" / "instances"
    for p in INST_VAULT.glob("*.json"):
        shutil.copy2(p, dst / p.name)


def setup_module(module):  # noqa: ARG001
    _restore_vault()
    _rebuild()
    _run(reset=True)


def test_rebuild_and_reset_run():
    rep = json.loads(REPORT.read_text())
    assert rep["generation"] == 1
    assert rep["policy_epoch"] == 4
    assert _audit() == "aligned"


def test_soft_matches_reference():
    rep = json.loads(REPORT.read_text())
    prof = _profile(rep, "soft")
    expect = _eval_file(INST_VAULT / "soft.json")
    assert prof["accepted"] is True
    assert prof["plan_digest_hex"] == expect["plan_digest_hex"]
    assert abs(prof["wasserstein"] - expect["wasserstein"]) <= TOL
    assert _probe("soft") == expect["plan_digest_hex"]
    assert abs(float(_probe_w("soft")) - expect["wasserstein"]) <= TOL


def test_spike_small_epsilon_log_domain():
    rep = json.loads(REPORT.read_text())
    prof = _profile(rep, "spike")
    expect = _eval_file(INST_VAULT / "spike.json")
    assert prof["accepted"] is True
    assert prof["plan_digest_hex"] == expect["plan_digest_hex"]
    assert abs(prof["wasserstein"] - expect["wasserstein"]) <= TOL
    assert math.isfinite(prof["wasserstein"])


def test_ridge_adversarial_epsilon():
    rep = json.loads(REPORT.read_text())
    prof = _profile(rep, "ridge")
    expect = _eval_file(INST_VAULT / "ridge.json")
    assert prof["accepted"] is True
    assert prof["plan_digest_hex"] == expect["plan_digest_hex"]
    assert abs(prof["wasserstein"] - expect["wasserstein"]) <= TOL


def test_anneal_warm_start_schedule():
    rep = json.loads(REPORT.read_text())
    prof = _profile(rep, "anneal")
    expect = _eval_file(INST_VAULT / "anneal.json")
    assert prof["accepted"] is True
    assert prof["plan_digest_hex"] == expect["plan_digest_hex"]
    assert abs(prof["wasserstein"] - expect["wasserstein"]) <= TOL


def test_rejects_badmass_and_badshape():
    rep = json.loads(REPORT.read_text())
    assert _profile(rep, "badmass")["accepted"] is False
    assert _profile(rep, "badshape")["accepted"] is False
    assert _profile(rep, "badmass")["plan_digest_hex"] == ""
    assert _profile(rep, "badshape")["wasserstein"] == 0


def test_plan_trace_csv_consistency():
    rep = json.loads(REPORT.read_text())
    with TRACE.open() as f:
        rows = list(csv.DictReader(f))
    for label in ("soft", "spike", "ridge", "anneal"):
        prof = _profile(rep, label)
        expect = _eval_file(INST_VAULT / f"{label}.json")
        label_rows = [r for r in rows if r["label"] == label]
        assert len(label_rows) == prof["rows"] * prof["cols"]
        for r in label_rows:
            i, j = int(r["i"]), int(r["j"])
            assert abs(float(r["p_ij"]) - expect["plan"][i][j]) <= TOL


def test_probe_inspect_cross_surface():
    rep = json.loads(REPORT.read_text())
    for label in ("soft", "spike", "ridge", "anneal"):
        prof = _profile(rep, label)
        assert _inspect(label) == prof["instance_id"]
        assert _probe(label) == prof["plan_digest_hex"]


def test_cache_and_ledger_agree():
    rep = json.loads(REPORT.read_text())
    cache = json.loads(CACHE.read_text())
    ledger = json.loads(LEDGER.read_text())
    assert ledger["generation"] == 1
    assert ledger["policy_epoch"] == 4
    entries = cache.get("entries", cache)
    for label in ("soft", "spike", "ridge", "anneal"):
        prof = _profile(rep, label)
        expect = _eval_file(INST_VAULT / f"{label}.json")
        key = expect["instance_digest_hex"] + "|4"
        assert key in entries
        assert entries[key]["plan_digest_hex"] == prof["plan_digest_hex"]
        assert abs(entries[key]["wasserstein"] - prof["wasserstein"]) <= TOL
        assert ledger["entries"][label]["plan_digest_hex"] == prof["plan_digest_hex"]
        assert ledger["entries"][label]["stable_runs"] == 1
    assert "badmass" not in ledger["entries"]


def test_generation_and_stable_runs_increment():
    _run(reset=False)
    rep = json.loads(REPORT.read_text())
    assert rep["generation"] == 2
    ledger = json.loads(LEDGER.read_text())
    assert ledger["generation"] == 2
    assert ledger["entries"]["soft"]["stable_runs"] == 2
    assert _audit() == "aligned"


def test_policy_epoch_cache_invalidation():
    _run(reset=True, env={"MASS_POLICY_EPOCH": "9"})
    rep = json.loads(REPORT.read_text())
    assert rep["policy_epoch"] == 9
    cache = json.loads(CACHE.read_text())
    entries = cache.get("entries", cache)
    soft = _eval_file(INST_VAULT / "soft.json")
    assert soft["instance_digest_hex"] + "|9" in entries
    assert soft["instance_digest_hex"] + "|0" not in entries
    assert soft["instance_digest_hex"] + "|4" not in entries


def test_mutated_epsilon_changes_plan():
    _restore_vault()
    dst = ROOT / "data" / "instances" / "soft.json"
    inst = json.loads(dst.read_text())
    inst["epsilon"] = 0.25
    dst.write_text(json.dumps(inst, indent=2) + "\n")
    _run(reset=True)
    rep = json.loads(REPORT.read_text())
    expect = _solve_instance(inst)
    prof = _profile(rep, "soft")
    assert prof["plan_digest_hex"] == expect["plan_digest_hex"]
    assert abs(prof["wasserstein"] - expect["wasserstein"]) <= TOL
    _restore_vault()
    _run(reset=True)


def test_mutated_cost_matrix():
    _restore_vault()
    dst = ROOT / "data" / "instances" / "spike.json"
    inst = json.loads(dst.read_text())
    inst["cost"][0][1] = float(inst["cost"][0][1]) + 3.5
    dst.write_text(json.dumps(inst, indent=2) + "\n")
    _run(reset=True)
    rep = json.loads(REPORT.read_text())
    expect = _solve_instance(inst)
    prof = _profile(rep, "spike")
    assert prof["accepted"] is True
    assert prof["plan_digest_hex"] == expect["plan_digest_hex"]
    _restore_vault()
    _run(reset=True)


def test_probe_rejects_unknown():
    rc = subprocess.run(
        [str(BUILD / "otctl-probe"), "nope"], capture_output=True
    ).returncode
    assert rc == 2
    rc = subprocess.run(
        [str(BUILD / "otctl-inspect"), "nope"], capture_output=True
    ).returncode
    assert rc == 2


def test_static_output_bypass_fails():
    REPORT.write_text("{}")
    TRACE.write_text("label,i,j,p_ij,c_ij\n")
    _rebuild()
    _run(reset=True)
    rep = json.loads(REPORT.read_text())
    assert _profile(rep, "spike")["accepted"] is True
    assert len(rep["profiles"]) >= 4
