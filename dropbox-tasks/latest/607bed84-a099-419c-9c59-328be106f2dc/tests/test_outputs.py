#!/usr/bin/env python3
"""Verifier for basinspan-weight-align-lab."""
from __future__ import annotations

import csv
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path("/app/environment")
BUILD = ROOT / "build"
OUTPUT = Path("/app/output")
VAR = Path("/app/var/basinspan")
REPORT = OUTPUT / "merge_report.json"
TRACE = OUTPUT / "alignment_trace.csv"
JOURNAL = OUTPUT / "merge_journal.jsonl"
CERT = OUTPUT / "barrier_certificate.json"
CACHE = VAR / "align_cache.json"
LEDGER = VAR / "merge_ledger.json"
VAULT = Path("/var/lib/verifier/pairs-vault")
PAIR_DIR = ROOT / "data" / "pairs"
POLICY_PATH = ROOT / "data" / "policy.json"


def sha256_hex(data: bytes | str) -> str:
    if isinstance(data, str):
        data = data.encode()
    proc = subprocess.run(
        ["python3", str(ROOT / "tools" / "parity_sha.py"), "file", "-"],
        input=data,
        capture_output=True,
        check=True,
    )
    return proc.stdout.decode().strip()


def sha256_line(line: str) -> str:
    proc = subprocess.run(
        ["python3", str(ROOT / "tools" / "parity_sha.py"), "hex", line],
        capture_output=True,
        check=True,
    )
    return proc.stdout.decode().strip()


def relu(x: float) -> float:
    return x if x > 0 else 0.0


def matvec(W, x):
    return [sum(wi * xi for wi, xi in zip(row, x)) for row in W]


def forward(model: dict, x: list[float]) -> list[float]:
    h = x
    layers = model["layers"]
    for i, layer in enumerate(layers):
        out = [a + b for a, b in zip(matvec(layer["W"], h), layer["b"])]
        if i < len(layers) - 1:
            h = [relu(v) for v in out]
        else:
            h = out
    return h


def layer_activations(model: dict, samples: list[list[float]], layer_idx: int) -> list[list[float]]:
    acts = []
    for x in samples:
        h = x
        layers = model["layers"]
        for i in range(layer_idx + 1):
            out = [a + b for a, b in zip(matvec(layers[i]["W"], h), layers[i]["b"])]
            if i < layer_idx:
                h = [relu(v) for v in out]
            else:
                h = [relu(v) for v in out] if i < len(layers) - 1 else out
        acts.append(h)
    return acts


def pearson(a: list[float], b: list[float]) -> float:
    n = len(a)
    ma = sum(a) / n
    mb = sum(b) / n
    va = sum((x - ma) ** 2 for x in a)
    vb = sum((x - mb) ** 2 for x in b)
    if va < 1e-12 or vb < 1e-12:
        return 0.0
    cov = sum((a[i] - ma) * (b[i] - mb) for i in range(n))
    return cov / (va**0.5 * vb**0.5)


def activation_correlation(acts_a, acts_b):
    d = len(acts_a[0])
    C = [[0.0] * d for _ in range(d)]
    for i in range(d):
        col_a = [acts_a[s][i] for s in range(len(acts_a))]
        for j in range(d):
            col_b = [acts_b[s][j] for s in range(len(acts_b))]
            C[i][j] = pearson(col_a, col_b)
    return C


def hungarian(cost):
    n = len(cost)
    u = [0.0] * (n + 1)
    v = [0.0] * (n + 1)
    p = [0] * (n + 1)
    way = [0] * (n + 1)
    for i in range(1, n + 1):
        p[0] = i
        j0 = 0
        minv = [float("inf")] * (n + 1)
        used = [False] * (n + 1)
        while True:
            used[j0] = True
            i0 = p[j0]
            delta = float("inf")
            j1 = 0
            for j in range(1, n + 1):
                if used[j]:
                    continue
                cur = cost[i0 - 1][j - 1] - u[i0] - v[j]
                if cur < minv[j]:
                    minv[j] = cur
                    way[j] = j0
                if minv[j] < delta:
                    delta = minv[j]
                    j1 = j
            for j in range(n + 1):
                if used[j]:
                    u[p[j]] += delta
                    v[j] -= delta
                else:
                    minv[j] -= delta
            j0 = j1
            if p[j0] == 0:
                break
        while True:
            j1 = way[j0]
            p[j0] = p[j1]
            j0 = j1
            if j0 == 0:
                break
    assign = [0] * n
    for j in range(1, n + 1):
        assign[p[j] - 1] = j - 1
    return assign


def permute_rows(W, b, perm):
    new_W = [W[perm[i]][:] for i in range(len(W))]
    new_b = [b[perm[i]] for i in range(len(b))]
    return new_W, new_b


def permute_cols(W, perm):
    return [[row[perm[j]] for j in range(len(perm))] for row in W]


def align_model_b(model_b, perms):
    layers = deepcopy_layers(model_b["layers"])
    hidden = len(perms)
    for li in range(hidden):
        perm = perms[li]
        W, b = permute_rows(layers[li]["W"], layers[li]["b"], perm)
        layers[li] = {"W": W, "b": b}
        if li + 1 < len(layers):
            layers[li + 1]["W"] = permute_cols(layers[li + 1]["W"], perm)
    if hidden > 0:
        layers[-1]["W"] = permute_cols(layers[-1]["W"], perms[-1])
    return {"layers": layers}


def deepcopy_layers(layers):
    return [{"W": [row[:] for row in layer["W"]], "b": layer["b"][:]} for layer in layers]


def average_models(model_a, model_b, weight=0.5):
    layers = []
    for la, lb in zip(model_a["layers"], model_b["layers"]):
        W = [[weight * a + (1 - weight) * b for a, b in zip(ra, rb)] for ra, rb in zip(la["W"], lb["W"])]
        b = [weight * a + (1 - weight) * b for a, b in zip(la["b"], lb["b"])]
        layers.append({"W": W, "b": b})
    return {"layers": layers}


def mse(model, ref_model, samples):
    err = 0.0
    for x in samples:
        ya = forward(ref_model, x)
        yb = forward(model, x)
        err += sum((a - b) ** 2 for a, b in zip(ya, yb)) / len(ya)
    return err / len(samples)


def align_merge(pair: dict, merge_weight: float = 0.5) -> dict:
    arch = pair["arch"]
    hidden = arch["hidden_dims"]
    acts_a_layers = []
    acts_b_layers = []
    for li in range(len(hidden)):
        acts_a_layers.append(layer_activations(pair["model_a"], pair["align_samples"], li))
        acts_b_layers.append(layer_activations(pair["model_b"], pair["align_samples"], li))

    perms = []
    trace = []
    align_cost = 0.0
    for li, d in enumerate(hidden):
        C = activation_correlation(acts_a_layers[li], acts_b_layers[li])
        cost = [[1.0 - max(0.0, C[i][j]) for j in range(d)] for i in range(d)]
        perm = hungarian(cost)
        perms.append(perm)
        for i in range(d):
            j = perm[i]
            align_cost += cost[i][j]
            trace.append({
                "layer": li,
                "neuron_a": i,
                "neuron_b": j,
                "correlation": round(C[i][j], 6),
                "assignment_cost": round(cost[i][j], 6),
            })

    aligned_b = align_model_b(pair["model_b"], perms)
    merged = average_models(pair["model_a"], aligned_b, merge_weight)
    naive = average_models(pair["model_a"], pair["model_b"], merge_weight)
    eval_mse = mse(merged, pair["model_a"], pair["eval_samples"])
    naive_mse = mse(naive, pair["model_a"], pair["eval_samples"])
    barrier = naive_mse - eval_mse
    perm_str = ";".join(",".join(str(x) for x in p) for p in perms)
    digest = sha256_line(f"layers={len(hidden)}|mse={eval_mse:.6f}|cost={align_cost:.6f}|perms={perm_str}")
    return {
        "align_cost": round(align_cost, 6),
        "eval_mse": round(eval_mse, 6),
        "naive_mse": round(naive_mse, 6),
        "barrier_value": round(barrier, 6),
        "permutations": perms,
        "trace": trace,
        "merge_digest_hex": digest,
    }


def valid_pair(pair: dict) -> bool:
    arch = pair.get("arch", {})
    for key in ("input_dim", "output_dim", "hidden_dims"):
        if key not in arch:
            return False
    hidden = arch["hidden_dims"]
    if not hidden:
        return False
    dims = [arch["input_dim"], *hidden, arch["output_dim"]]
    for model_key in ("model_a", "model_b"):
        m = pair.get(model_key, {})
        layers = m.get("layers", [])
        if len(layers) != len(hidden) + 1:
            return False
        for i, layer in enumerate(layers):
            out_d, in_d = dims[i + 1], dims[i]
            W = layer.get("W", [])
            b = layer.get("b", [])
            if len(W) != out_d or any(len(row) != in_d for row in W):
                return False
            if len(b) != out_d:
                return False
    return True


def load_policy() -> dict:
    pol = json.loads(POLICY_PATH.read_text())
    if os.environ.get("BASINSPAN_POLICY_EPOCH"):
        pol["policy_epoch"] = int(os.environ["BASINSPAN_POLICY_EPOCH"])
    return pol


def report_digest(gen: int, epoch: int, digests: list[str]) -> str:
    ds = sorted(digests)
    return sha256_line(f"gen={gen}|epoch={epoch}|digests={','.join(ds)}")


def cert_digest(label: str, barrier: float, eval_mse: float, perms: list[list[int]]) -> str:
    flat = ";".join(",".join(str(x) for x in p) for p in perms)
    return sha256_line(f"label={label}|barrier={barrier:.6f}|mse={eval_mse:.6f}|perms={flat}")


def rebuild() -> None:
    subprocess.run(["/app/environment/scripts/rebuild.sh"], check=True)


def run_cli(reset: bool = True, env: dict | None = None) -> None:
    merged = os.environ.copy()
    if env:
        merged.update(env)
    if reset:
        subprocess.run([str(BUILD / "basinspan-run"), "--reset"], check=True, env=merged)
    else:
        subprocess.run([str(BUILD / "basinspan-run")], check=True, env=merged)


def probe(label: str) -> str:
    return subprocess.check_output([str(BUILD / "basinspan-probe"), label], text=True).strip()


def audit(label: str) -> str:
    return subprocess.check_output([str(BUILD / "basinspan-audit"), label], text=True).strip()


def inspect_out() -> str:
    return subprocess.check_output([str(BUILD / "basinspan-inspect")], text=True).strip()


def restore_vault() -> None:
    if VAULT.is_dir():
        for p in PAIR_DIR.glob("*.json"):
            p.unlink()
        for src in VAULT.glob("*.json"):
            shutil.copy(src, PAIR_DIR / src.name)


@pytest.fixture(scope="module", autouse=True)
def _setup() -> None:
    rebuild()
    restore_vault()
    run_cli(reset=True)


def test_binaries() -> None:
    for name in ("basinspan-run", "basinspan-probe", "basinspan-audit", "basinspan-inspect"):
        assert (BUILD / name).is_file()


def test_reference_pearson_alignment() -> None:
    pair = json.loads((PAIR_DIR / "alpha.json").read_text())
    ref = align_merge(pair)
    assert ref["barrier_value"] > 0.001
    assert ref["eval_mse"] < ref["naive_mse"]


def test_full_campaign_reset() -> None:
    run_cli(reset=True)
    rep = json.loads(REPORT.read_text())
    pol = load_policy()
    assert rep["generation"] == 1
    assert rep["policy_epoch"] == pol["policy_epoch"]
    by = {p["label"]: p for p in rep["profiles"]}
    assert not by["invalid"]["accepted"]
    assert by["invalid"]["merge_digest_hex"] == ""
    accepted_digests = []
    for label in ("alpha", "beta", "gamma"):
        pair = json.loads((PAIR_DIR / f"{label}.json").read_text())
        ref = align_merge(pair, pol["merge_weight"])
        p = by[label]
        assert p["accepted"]
        assert abs(p["eval_mse"] - ref["eval_mse"]) < 1e-4
        assert abs(p["align_cost"] - ref["align_cost"]) < 1e-4
        assert abs(p["barrier_value"] - ref["barrier_value"]) < 1e-4
        assert p["merge_digest_hex"] == ref["merge_digest_hex"]
        accepted_digests.append(p["merge_digest_hex"])
        pr = probe(label)
        assert pr == (
            f"mse={p['eval_mse']}|barrier={p['barrier_value']}|"
            f"digest={p['merge_digest_hex']}"
        )
    assert "report_digest_hex" in rep
    assert rep["report_digest_hex"] == report_digest(
        rep["generation"], rep["policy_epoch"], accepted_digests
    )


def test_cross_artifacts() -> None:
    run_cli(reset=True)
    rep = json.loads(REPORT.read_text())
    rows = list(csv.DictReader(TRACE.open()))
    journal = [json.loads(ln) for ln in JOURNAL.read_text().splitlines() if ln.strip()]
    for p in rep["profiles"]:
        if not p["accepted"]:
            continue
        j = next(x for x in journal if x["label"] == p["label"])
        assert abs(j["eval_mse"] - p["eval_mse"]) < 1e-6
        assert abs(j["barrier_value"] - p["barrier_value"]) < 1e-6
        layer_rows = [r for r in rows if r["label"] == p["label"]]
        arch = json.loads((PAIR_DIR / f"{p['label']}.json").read_text())["arch"]
        assert len(layer_rows) == sum(arch["hidden_dims"])


def test_barrier_certificate() -> None:
    run_cli(reset=True)
    cert = json.loads(CERT.read_text())
    rep = json.loads(REPORT.read_text())
    profile = next(x for x in rep["profiles"] if x["label"] == cert["label"] and x["accepted"])
    pair = json.loads((PAIR_DIR / f"{cert['label']}.json").read_text())
    ref = align_merge(pair)
    assert abs(cert["eval_mse"] - profile["eval_mse"]) < 1e-4
    assert abs(cert["barrier_value"] - profile["barrier_value"]) < 1e-4
    assert cert["permutations"] == ref["permutations"]
    assert abs(cert["barrier_value"] - ref["barrier_value"]) < 1e-4
    assert cert["cert_digest_hex"] == cert_digest(cert["label"], cert["barrier_value"], cert["eval_mse"], cert["permutations"])
    assert audit(cert["label"]) == f"cert_barrier={cert['barrier_value']}|cert_mse={cert['eval_mse']}"


def test_generation_without_reset() -> None:
    run_cli(reset=True)
    run_cli(reset=False)
    rep = json.loads(REPORT.read_text())
    assert rep["generation"] == 2
    led = json.loads(LEDGER.read_text())
    assert led["generation"] == 2


def test_policy_epoch_cache_invalidation() -> None:
    run_cli(reset=True)
    run_cli(reset=False, env={"BASINSPAN_POLICY_EPOCH": "7"})
    cache = json.loads(CACHE.read_text())
    assert cache["policy_epoch"] == 7
    rep = json.loads(REPORT.read_text())
    beta = next(p for p in rep["profiles"] if p["label"] == "beta")
    pair = json.loads((PAIR_DIR / "beta.json").read_text())
    ref = align_merge(pair)
    assert abs(beta["eval_mse"] - ref["eval_mse"]) < 1e-4


def test_vault_restore_mutation() -> None:
    shutil.copy(VAULT / "alpha.json", PAIR_DIR / "alpha.json")
    pair = json.loads((PAIR_DIR / "alpha.json").read_text())
    pair["model_b"]["layers"][0]["b"][0] += 0.05
    (PAIR_DIR / "alpha.json").write_text(json.dumps(pair))
    run_cli(reset=True)
    rep = json.loads(REPORT.read_text())
    alpha = next(p for p in rep["profiles"] if p["label"] == "alpha")
    ref = align_merge(pair)
    assert abs(alpha["eval_mse"] - ref["eval_mse"]) < 1e-4


def test_inspect_stable_runs() -> None:
    run_cli(reset=True)
    run_cli(reset=False)
    out = inspect_out()
    rep = json.loads(REPORT.read_text())
    led = json.loads(LEDGER.read_text())
    total = sum(e["stable_runs"] for e in led["entries"].values())
    assert out == f"gen={rep['generation']}|stable_total={total}"


def test_reject_invalid() -> None:
    run_cli(reset=True)
    assert probe("invalid") == "reject:invalid"
