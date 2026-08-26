"""Verifier helpers — shared reference math and subprocess CLI runners.

Probe markers (tests-only): ingest-only poison and export-only lane traps are
covered by capture-only / egress-lane suites; do not treat as product vocabulary.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path

APP = Path("/app")
FIXTURES = Path(__file__).resolve().parent / "verifier-fixtures"
SERVICES = ("ledger-db", "identity-gate", "billing-core", "alert-dispatch")
ROLLBACK_STEPS = ("alert-dispatch", "identity-gate", "ledger-db")

PATH_RELEASE_STATE = "/app/data/deploy/release-state.json"
PATH_FORWARD_ORDER = "/app/data/deploy/forward-order.json"
PATH_ROLLBACK_GRAPH = "/app/data/topology/rollback-graph.json"
PATH_ROLLBACK_LOG = "/app/data/logs/rollback-events.jsonl"
PATH_DEPLOY_STATUS = "/app/state/deploy-status.json"
PATH_INSPECT_MANIFEST = "/app/state/inspect-manifest.json"
PATH_ROLLBACK_PLAN = "/app/output/rollback-plan.json"
PATH_PLAN_SEAL = "/app/state/plan-seal.json"
PATH_ROLLBACK_COMPLETE = "/app/state/rollback-complete.ok"
PATH_INCIDENT_REGISTRY = "/app/data/incident/registry.json"
PATH_TRUTH_LEDGER = "/app/state/truth-ledger.json"
PATH_WAVE_SNAPSHOT = "/app/state/wave-midpipe-snapshot.json"
PATH_EGRESS_LANE = "/app/state/egress-lane-midpipe.json"
PATH_RUN_LEDGER = "/app/state/rollback-run-ledger.json"
PATH_WITNESS_BUNDLE = "/app/state/rollback-witness-bundle.json"


def reference_plan_hash(steps: list[str], release: str) -> str:
    lines = [f"release|{release}"]
    for step in sorted(steps):
        lines.append(f"step|{step}")
    return hashlib.sha256("\n".join(lines).encode()).hexdigest()


def reference_release_digest(status: dict) -> str:
    order = json.loads((APP / "data/deploy/forward-order.json").read_text())
    lines = [
        f"{svc}|{status['services'][svc]['status']}"
        for svc in order
        if svc in status["services"]
    ]
    return hashlib.sha256("\n".join(lines).encode()).hexdigest()


def reference_release_digest_lexsort(status: dict) -> str:
    lines = sorted(f"{svc}|{status['services'][svc]['status']}" for svc in status["services"])
    return hashlib.sha256("\n".join(lines).encode()).hexdigest()


def reference_forward_digest() -> str:
    order = json.loads((APP / "data/deploy/forward-order.json").read_text())
    return hashlib.sha256("\n".join(order).encode()).hexdigest()


def reference_deploy_status() -> dict:
    return json.loads((APP / "data/deploy/release-state.json").read_text())


def reference_rollback_steps() -> list[str]:
    return list(ROLLBACK_STEPS)


def reference_wave_step_sequence_digest(steps: list[str]) -> str:
    lines = [f"wave|{idx}|{step}" for idx, step in enumerate(steps)]
    return hashlib.sha256("\n".join(lines).encode()).hexdigest()


def reference_midpipe_chain_digest(
    capture_seq: int,
    plan_hash: str,
    release_digest: str,
    wave_step_sequence_digest: str,
) -> str:
    lines = [
        f"capture|{capture_seq}",
        f"plan|{plan_hash}",
        f"release|{release_digest}",
        f"wave|{wave_step_sequence_digest}",
    ]
    return hashlib.sha256("\n".join(lines).encode()).hexdigest()


def reference_zone_quorum_token(
    incident_id: str,
    zone: str,
    midpipe_chain_digest: str,
    capture_seq: int,
    plan_hash: str,
) -> str:
    lines = [
        f"incident|{incident_id}",
        f"zone|{zone}",
        f"chain|{midpipe_chain_digest}",
        f"capture|{capture_seq}",
        f"plan|{plan_hash}",
    ]
    return hashlib.sha256("\n".join(lines).encode()).hexdigest()


def pipeline_through_validate() -> None:
    _rebuild_ctl()
    proc = _run(["/app/bin/rollbackctl", "inspect"])
    assert proc.returncode == 0, proc.stderr + proc.stdout
    proc = _run(["/app/bin/rollbackctl", "plan"])
    assert proc.returncode == 0, proc.stderr + proc.stdout
    validate_ok()


def validate_ok() -> None:
    proc = _run(["/app/bin/rollbackctl", "validate"])
    assert proc.returncode == 0, proc.stderr + proc.stdout


def _run(cmd: list[str], env: dict | None = None) -> subprocess.CompletedProcess:
    run_env = os.environ.copy()
    if env:
        run_env.update(env)
    return subprocess.run(cmd, capture_output=True, text=True, env=run_env, cwd=str(APP))


def _rebuild_ctl() -> None:
    env = os.environ.copy()
    env["PATH"] = "/usr/local/go/bin:/usr/local/bin:/usr/bin:" + env.get("PATH", "")
    proc = subprocess.run(
        ["go", "build", "-o", "/app/bin/rollbackctl", "./cmd/rollbackctl"],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(APP),
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout


class TestFleetRolloutApplyContracts:
    """Category-native system-administration checks for pack Layer 10."""

    def test_wave_order_follows_topology_reverse_deps(self):
        """rollout wave steps follow topology reverse-dependency order on the fleet graph."""
        pipeline_through_validate()
        plan = json.loads(Path(PATH_ROLLBACK_PLAN).read_text())
        assert plan["steps"] == list(ROLLBACK_STEPS)

    def test_inspect_manifest_binds_forward_host_sequence(self):
        """inspect-manifest release_digest binds deploy status in forward-order host sequence."""
        pipeline_through_validate()
        manifest = json.loads(Path(PATH_INSPECT_MANIFEST).read_text())
        status = json.loads(Path(PATH_DEPLOY_STATUS).read_text())
        assert manifest["release_digest"] == reference_release_digest(status)

    def test_apply_blocks_poisoned_egress_lane_digest(self):
        """apply rejects stale egress-lane midpipe_chain_digest before host promotion."""
        pipeline_through_validate()
        lane_path = Path(PATH_EGRESS_LANE)
        lane = json.loads(lane_path.read_text())
        lane["midpipe_chain_digest"] = "0" * 64
        lane_path.write_text(json.dumps(lane, indent=2) + "\n")
        status = json.loads((APP / "state/deploy-status.json").read_text())
        proc = _run(
            ["/app/deploy/scripts/apply-rollback.sh"],
            env={
                "ROLLBACK_INCIDENT_ID": status["incident_id"],
                "ROLLBACK_ZONE": "primary",
            },
        )
        assert proc.returncode != 0

    def test_apply_requires_zone_witness_bundle_file(self):
        """fleet apply exits non-zero when rollback-witness-bundle.json is missing."""
        _rebuild_ctl()
        _run(["/app/bin/rollbackctl", "inspect"])
        _run(["/app/bin/rollbackctl", "plan"])
        Path(PATH_WITNESS_BUNDLE).unlink(missing_ok=True)
        status = json.loads((APP / "state/deploy-status.json").read_text())
        proc = _run(
            ["/app/deploy/scripts/apply-rollback.sh"],
            env={
                "ROLLBACK_INCIDENT_ID": status["incident_id"],
                "ROLLBACK_ZONE": "primary",
            },
        )
        assert proc.returncode != 0

    def test_plan_hash_matches_sorted_step_reference(self):
        """rollback-plan hash matches reference topology wave digest for fleet steps."""
        pipeline_through_validate()
        plan = json.loads(Path(PATH_ROLLBACK_PLAN).read_text())
        assert plan["hash"] == reference_plan_hash(plan["steps"], plan["release"])