"""End-to-end oracle for the AI workflow runtime recovery & replay engine.

Validates only through complete pipeline execution and independent recomputation.
Does not name individual package defects.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import shutil
import subprocess
import unicodedata
from pathlib import Path

import pytest

ROOT = Path(os.environ.get("RUNTIME_ROOT") or os.environ.get("TB3_APP_ROOT") or "/app")
BIN = os.environ.get("RUNTIME_BIN") or "/tmp/runtime"
EPOCH = "2024-06-15T12:00:00Z"
TOKEN = "workflow-runtime-hmac-token-v1"
SEED = "workflow-runtime-v1"

REQUIRED = (
    "state/normalized.json",
    "state/compiled.json",
    "state/schedule.json",
    "state/execution.json",
    "state/journal.json",
    "state/checkpoints.json",
    "state/recovery.json",
    "state/replay.json",
    "state/verification.json",
    "output/certificate.json",
    "output/verification.json",
    "output/recovery.json",
    "output/replay.json",
)


def domain_hash(domain: str, payload: bytes) -> str:
    return hashlib.sha256(domain.encode() + b"\n" + payload).hexdigest()


def canon(value):
    if isinstance(value, dict):
        return {k: canon(value[k]) for k in sorted(value)}
    if isinstance(value, list):
        return [canon(x) for x in value]
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def canon_json(value) -> bytes:
    return json.dumps(canon(value), separators=(",", ":"), ensure_ascii=False).encode()


def expected_workflow_id(name: str, version: str) -> str:
    return domain_hash("workflow-id", f"{name}\n{version}".encode())[:16]


def expected_plan_order() -> list[str]:
    return ["audit", "ingest", "normalize", "feature", "evaluate", "train", "publish"]


def reference_certificate(body: dict, token: str) -> tuple[str, str]:
    payload = canon_json(body)
    body_digest = domain_hash("recovery-certificate-v1", payload)
    sig = hmac.new(token.encode(), payload, hashlib.sha256).hexdigest()
    return body_digest, sig


def load(rel: str):
    return json.loads((ROOT / rel).read_text())


def clean():
    for name in ("state", "output", "cache"):
        shutil.rmtree(ROOT / name, ignore_errors=True)
        (ROOT / name).mkdir(parents=True, exist_ok=True)
    (ROOT / "state" / "checkpoints").mkdir(parents=True, exist_ok=True)


def runtime_env():
    return os.environ | {
        "PATH": f"/usr/local/go/bin:/tmp:/usr/local/bin:{os.environ.get('PATH', '')}",
        "RUNTIME_ROOT": str(ROOT),
        "RUNTIME_BIN": BIN,
        "RUNTIME_MAX_RETRIES": "2",
        "RUNTIME_TIMEOUT_MS": "100",
        "RUNTIME_SEED": SEED,
        "RUNTIME_EPOCH": EPOCH,
        "RUNTIME_STRICT_MODE": "true",
        "RUNTIME_WORKERS": "w0,w1,w2",
        "RUNTIME_CHECKPOINT_EVERY": "2",
        "VERBOSE": "0",
    }


def rebuild_binary():
    global BIN
    target = Path(os.environ.get("RUNTIME_BIN") or "/tmp/runtime")
    result = subprocess.run(
        ["go", "build", "-o", str(target), "./cmd/runtime"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        env=runtime_env(),
    )
    assert result.returncode == 0, f"go build failed:\n{result.stderr or result.stdout}"
    BIN = str(target)
    os.environ["RUNTIME_BIN"] = BIN
    return BIN


def run_pipeline(check: bool = True):
    clean()
    return subprocess.run(
        ["bash", str(ROOT / "scripts/run_pipeline.sh")],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        env=runtime_env(),
        check=check,
    )


@pytest.fixture(scope="module", autouse=True)
def _build_and_run():
    rebuild_binary()
    result = run_pipeline(check=False)
    assert result.returncode == 0, f"pipeline failed:\n{result.stderr or result.stdout}"


def test_required_artifacts_exist():
    """Stage A–H must materialize the required state/ and output/ artifacts."""
    missing = [p for p in REQUIRED if not (ROOT / p).exists()]
    assert missing == [], f"missing artifacts: {missing}"


def test_workflow_identity_and_normalization():
    """Stage A: NFC names, metadata keys, and DomainHash(name+\\n+version) workflow id."""
    wf = load("state/normalized.json")
    assert wf["name"] == "AI Training Workflow"
    assert wf["version"] == "2.1.0"
    # Epoch / env-over-file precedence is covered by test_policy_env_overrides_file.
    assert wf["id"] == expected_workflow_id(wf["name"], wf["version"])
    for node in wf["nodes"]:
        assert unicodedata.is_normalized("NFC", node["name"])
    assert set(wf["metadata"]) == {"owner", "team", "region", "priority"}


def test_dag_order_and_coverage():
    """Stage B: plan order covers all nodes with dependencies preceding dependents."""
    wf = load("state/normalized.json")
    plan = load("state/compiled.json")
    assert plan["order"] == expected_plan_order()
    assert set(plan["order"]) == {n["id"] for n in wf["nodes"]}
    index = {nid: i for i, nid in enumerate(plan["order"])}
    for n in wf["nodes"]:
        for dep in n.get("depends_on") or []:
            assert index[dep] < index[n["id"]], f"{dep} must precede {n['id']}"


def test_scheduler_workers_and_timeouts():
    """Stage C: ascending workers and env policy retries/timeouts over plan order."""
    sched = load("state/schedule.json")
    plan = load("state/compiled.json")
    assignments = sched["assignments"]
    assert [a["node_id"] for a in assignments] == plan["order"]
    workers = sorted(["w0", "w1", "w2"])
    for i, a in enumerate(assignments):
        assert a["worker_id"] == workers[i % 3]
        assert a["timeout_ms"] == 100
        assert a["max_retries"] == 2


def test_execution_journal_and_determinism():
    """Stage C: completed execution and independently recomputed journal-v1 DomainHash."""
    rec = load("state/execution.json")
    journal = load("state/journal.json")
    assert rec["status"] == "completed"
    assert len(rec["results"]) == 7
    assert all(r["status"] == "ok" for r in rec["results"])
    assert [e["seq"] for e in journal["entries"]] == list(range(len(journal["entries"])))
    entries = sorted(journal["entries"], key=lambda e: e["seq"])
    payload = {
        "entries": [
            {
                "action": e["action"],
                "digest": e["digest"],
                "meta": e.get("meta") or {},
                "node_id": e["node_id"],
                "seq": e["seq"],
            }
            for e in entries
        ],
        "workflow_id": journal["workflow_id"],
    }
    expected = domain_hash("journal-v1", canon_json(payload))
    assert rec["journal_hash"] == expected
    assert journal["workflow_id"] == rec["workflow_id"]


def test_checkpoint_latest_and_integrity():
    """Stage D/E: Latest checkpoint version and recovered completed set cover all nodes."""
    cps = load("state/checkpoints.json")
    latest = cps["latest"]
    assert latest["version"] >= 2
    recovered = load("state/recovered_checkpoint.json")
    assert recovered["workflow_id"] == load("state/normalized.json")["id"]
    assert set(recovered["completed"]) == {n["id"] for n in load("state/normalized.json")["nodes"]}


def test_recovery_and_replay():
    """Stage E/F: recovered status, epoch-relative second timestamps, digest match."""
    recovery = load("state/recovery.json")
    replay = load("state/replay.json")
    rec = load("state/execution.json")
    assert recovery["final_status"] == "recovered"
    assert recovery["recovery_digest"]
    assert replay["epoch"] == EPOCH
    assert [e["seq"] for e in replay["events"]] == sorted(e["seq"] for e in replay["events"])
    for e in replay["events"]:
        assert "T" in e["timestamp"] and "." not in e["timestamp"]
    digests = {r["node_id"]: r["digest"] for r in rec["results"]}
    for e in replay["events"]:
        if e["action"] in ("ok", "failed"):
            assert digests[e["node_id"]] == e["digest"]


def test_verification_all_green():
    """Stage G: lineage, graph, checkpoint, replay, and hash checks all pass."""
    report = load("output/verification.json")
    assert report["lineage_ok"] is True
    assert report["graph_ok"] is True
    assert report["checkpoint_ok"] is True
    assert report["replay_ok"] is True
    assert report["hash_ok"] is True
    assert report["issues"] == []


def test_certificate_hmac_and_bindings():
    """Stage H: HMAC-SHA256 certificate binds plan/journal/replay/recovery digests."""
    cert = load("output/certificate.json")
    status = load("output/certificate_status.json")
    rec = load("state/execution.json")
    replay = load("state/replay.json")
    recovery = load("state/recovery.json")
    report = load("state/verification.json")
    plan = load("state/compiled.json")
    wf = load("state/normalized.json")

    assert status["valid"] is True
    assert cert["replay_hash"] == replay["replay_hash"]
    assert cert["journal_hash"] == rec["journal_hash"]
    assert cert["plan_digest"] == plan["digest"]
    assert cert["recovery_digest"] == recovery["recovery_digest"]
    assert cert["verification_hash"] == report["verification_hash"]

    body = {
        "journal_hash": cert["journal_hash"],
        "plan_digest": cert["plan_digest"],
        "provenance": cert["provenance"],
        "recovery_digest": cert["recovery_digest"],
        "replay_hash": cert["replay_hash"],
        "verification_hash": cert["verification_hash"],
        "version": "recovery-certificate-v1",
        "workflow_id": wf["id"],
    }
    body_digest, sig = reference_certificate(body, TOKEN)
    assert cert["body_digest"] == body_digest
    assert cert["signature"] == sig


def test_reproducibility_byte_identical():
    """Repeated clean pipeline runs must produce byte-identical certificate digests."""
    cert1 = load("output/certificate.json")
    result = run_pipeline(check=False)
    assert result.returncode == 0, result.stderr or result.stdout
    cert2 = load("output/certificate.json")
    assert cert1["body_digest"] == cert2["body_digest"]
    assert cert1["signature"] == cert2["signature"]
    assert cert1["replay_hash"] == cert2["replay_hash"]
    assert load("state/compiled.json")["order"] == expected_plan_order()


def test_policy_env_overrides_file():
    """RUNTIME_* env values must override configs/policy.json for epoch and scheduling."""
    wf = load("state/normalized.json")
    assert wf["epoch"] == EPOCH
    sched = load("state/schedule.json")
    assert all(a["max_retries"] == 2 for a in sched["assignments"])
    assert all(a["timeout_ms"] == 100 for a in sched["assignments"])
