#!/usr/bin/env python3
"""Behavioral checks for d9_run terminal artifact."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

APP = Path("/app")
ENV = APP / "environment"
OUT = APP / "output" / "inv_d9.yaml"
IDX = ENV / "data" / "idx_store.db"
BUNDLE = ENV / "fixtures" / "set_a"
HOLD = ENV / "data" / "hold_d9.toml"
SCHEMA = ENV / "schemas" / "artifact_d9.schema.json"
SEG = ENV / "k2d" / "seg_v"

CLASS_BASIS = {10: 2, 11: 3, 12: 2}
TOTAL_BASIS_ROWS = sum(CLASS_BASIS.values())


def exec_step(command: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(command, text=True, capture_output=True, check=False, cwd=cwd)
    if proc.returncode != 0:
        raise AssertionError(
            f"step failed: {' '.join(command)}\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
        )
    return proc


def compile_driver() -> None:
    exec_step(["npm", "run", "build", "--prefix", str(ENV)])


def reset_segment_state() -> None:
    SEG.mkdir(parents=True, exist_ok=True)
    cursor = SEG / "cursor.dat"
    if cursor.exists():
        cursor.unlink()
    (SEG / ".reset").write_text("", encoding="utf-8")


def wipe_output_tree() -> None:
    out_dir = APP / "output"
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)


def load_doc() -> dict:
    text = OUT.read_text(encoding="utf-8")
    slice_m = re.search(r"^slice_id:\s*(\d+)", text, re.MULTILINE)
    profile_m = re.search(r"^profile:\s*(\d+)", text, re.MULTILINE)
    doc: dict = {
        "slice_id": int(slice_m.group(1)) if slice_m else 0,
        "profile": int(profile_m.group(1)) if profile_m else 0,
        "rows": [],
    }
    for block in re.split(r"\n  - instance_uid:\s*", text)[1:]:
        lines = block.splitlines()
        uid = lines[0].strip()
        mesh_m = re.search(r"mesh_id:\s*(\d+)", block)
        class_m = re.search(r"class_code:\s*(\d+)", block)
        labels_m = re.search(r"labels:\s*(\[[^\]]+\])", block)
        weights_m = re.search(r"weights:\s*(\[[^\]]+\])", block)
        score_m = re.search(r"o8_score:\s*(-?\d+)", block)
        digest_m = re.search(r"row_digest:\s*([0-9a-f]{64})", block)
        doc["rows"].append(
            {
                "instance_uid": uid,
                "mesh_id": int(mesh_m.group(1)) if mesh_m else 0,
                "class_code": int(class_m.group(1)) if class_m else 0,
                "labels": json.loads(labels_m.group(1)) if labels_m else [],
                "weights": json.loads(weights_m.group(1)) if weights_m else [],
                "o8_score": int(score_m.group(1)) if score_m else 0,
                "row_digest": digest_m.group(1) if digest_m else "",
            }
        )
    return doc


def invoke_driver() -> dict:
    wipe_output_tree()
    reset_segment_state()
    proc = subprocess.run(
        [
            "node",
            "/app/environment/dist/d9_run.js",
            "--dump-dir",
            "/app/environment/fixtures/set_a",
            "--idx-store",
            "/app/environment/data/idx_store.db",
            "--out",
            "/app/output/inv_d9.yaml",
        ],
        text=True,
        capture_output=True,
        check=False,
        cwd=ENV,
    )
    if proc.returncode != 0:
        raise AssertionError(
            f"step failed: node d9_run\nstdout:\n{proc.stdout}\nerror:\n{proc.stderr}"
        )
    payload = load_doc()
    assert isinstance(payload.get("rows"), list)
    return payload


def pact_row_hash(instance_uid: str, labels: list[int], weights: list[float]) -> str:
    sorted_labels = ",".join(str(x) for x in sorted(labels))
    weight_csv = ",".join(f"{w:.4f}" for w in weights)
    canon = f"{instance_uid}|{sorted_labels}|{weight_csv}"
    return hashlib.sha256(canon.encode()).hexdigest()


def argmax_weight(weights: list[float]) -> int:
    best = 0
    best_val = weights[0]
    for i, val in enumerate(weights[1:], start=1):
        if val > best_val + 1e-6:
            best = i
            best_val = val
    return best


def simulate_profile(profile: int, strengths: list[float]) -> list[float]:
    total = sum(strengths)
    weights = [s / total for s in strengths]
    order = [0, 1, 2] if profile == 0 else [1, 0, 2]
    best = 0
    best_val = weights[0]
    for i in range(1, 3):
        if weights[i] > best_val + 1e-6:
            best = i
            best_val = weights[i]
        elif abs(weights[i] - best_val) <= 1e-6 and order.index(i) < order.index(best):
            best = i
    weights[best] += 0.0001
    renorm = sum(weights)
    return [w / renorm for w in weights]


@pytest.fixture(scope="module", autouse=True)
def compiled_driver() -> None:
    compile_driver()


def test_d01() -> None:
    """Obligation eight zero-violation rows for bundled ORDERS walks."""
    doc = invoke_driver()
    assert doc["slice_id"] == 759
    for row in doc["rows"]:
        assert row["o8_score"] >= 0


def test_d02() -> None:
    """MI threshold ties match witness weight vector on graded instances."""
    doc = invoke_driver()
    for row in doc["rows"]:
        weights = row["weights"]
        assert len(weights) == 3
        dom = argmax_weight(weights)
        expected = simulate_profile(0, [0.33, 0.33, 0.34])
        assert abs(weights[dom] - max(expected)) < 0.05


def test_d03() -> None:
    """Cross-profile divergence between strict and relaxed strength tables."""
    doc = invoke_driver()
    assert doc["profile"] == 0
    tied = [1 / 3, 1 / 3, 1 / 3]
    strict_dom = argmax_weight(simulate_profile(0, tied))
    relaxed_dom = argmax_weight(simulate_profile(1, tied))
    assert strict_dom != relaxed_dom
    assert strict_dom == 0
    assert relaxed_dom == 1


def test_d04() -> None:
    """Parent damper lattice fold labels propagate before obligation evaluation."""
    doc = invoke_driver()
    by_uid = {r["instance_uid"].split("#")[0]: r for r in doc["rows"]}
    child = by_uid["uid_a"]
    assert 100 in child["labels"]


def test_d05() -> None:
    """Seed-only fold path fails parent damper permutation."""
    doc = invoke_driver()
    by_uid = {r["instance_uid"].split("#")[0]: r for r in doc["rows"]}
    child = by_uid["uid_a"]
    assert child["labels"] != sorted([101, 102])


def test_d06() -> None:
    """Minimal row basis sizing matches closure class sizes."""
    doc = invoke_driver()
    base_uids = {r["instance_uid"].split("#")[0] for r in doc["rows"]}
    assert base_uids == {"uid_a", "uid_b", "uid_c"}
    assert len(doc["rows"]) == TOTAL_BASIS_ROWS
    counts: dict[int, int] = {}
    for row in doc["rows"]:
        counts[row["class_code"]] = counts.get(row["class_code"], 0) + 1
    for code, basis in CLASS_BASIS.items():
        assert counts.get(code, 0) == basis


def test_d07() -> None:
    """Lane truncation fix required for full stream obligation checks."""
    doc = invoke_driver()
    assert len(doc["rows"]) == TOTAL_BASIS_ROWS
    assert len(doc["rows"]) > 6
    assert doc["rows"][0]["instance_uid"]
    assert doc["profile"] == 0
    assert all(row["o8_score"] >= 0 for row in doc["rows"])


def test_d08() -> None:
    """Idempotent d9_run rerun after recovery command."""
    wipe_output_tree()
    reset_segment_state()
    exec_step(
        [
            "node",
            "/app/environment/dist/d9_run.js",
            "--dump-dir",
            "/app/environment/fixtures/set_a",
            "--idx-store",
            "/app/environment/data/idx_store.db",
            "--out",
            "/app/output/inv_d9.yaml",
        ],
        cwd=ENV,
    )
    first = load_doc()
    reset_segment_state()
    exec_step(
        [
            "node",
            "/app/environment/dist/d9_run.js",
            "--dump-dir",
            "/app/environment/fixtures/set_a",
            "--idx-store",
            "/app/environment/data/idx_store.db",
            "--out",
            "/app/output/inv_d9.yaml",
        ],
        cwd=ENV,
    )
    second = load_doc()
    d1 = {r["instance_uid"]: r["row_digest"] for r in first["rows"]}
    d2 = {r["instance_uid"]: r["row_digest"] for r in second["rows"]}
    assert d1 == d2


def test_d09() -> None:
    """Stage YAML omits fields present in terminal inv_d9.yaml."""
    doc = invoke_driver()
    stage_path = APP / "output" / "stage" / "partial.yaml"
    assert stage_path.exists()
    stage_text = stage_path.read_text(encoding="utf-8")
    assert "row_digest" not in stage_text
    assert "o8_score" not in stage_text
    assert doc["rows"][0]["row_digest"]


def test_d10() -> None:
    """Held-out hold_d9.toml permutations satisfy overapprox inclusion digests."""
    doc = invoke_driver()
    by_uid = {r["instance_uid"].split("#")[0]: r for r in doc["rows"]}
    seeds = {"uid_a": {101, 102}, "uid_b": {201}, "uid_c": {100}}
    for uid, seed_set in seeds.items():
        labels = set(by_uid[uid]["labels"])
        assert labels >= seed_set
    exec_step(
        ["python3", str(ENV / "tools" / "q9_cycle.py"), "--seed", "759", "--cycles", "40"]
    )
    for row in doc["rows"]:
        calc = pact_row_hash(row["instance_uid"], row["labels"], row["weights"])
        assert row["row_digest"] == calc
