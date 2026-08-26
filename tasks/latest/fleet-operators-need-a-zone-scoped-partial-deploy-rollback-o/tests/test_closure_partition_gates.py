"""Closure partition gates tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from test_outputs import (
    APP,
    PATH_INCIDENT_REGISTRY,
    PATH_INSPECT_MANIFEST,
    PATH_PLAN_SEAL,
    PATH_ROLLBACK_PLAN,
    _rebuild_ctl,
    _run,
    reference_rollback_steps,
    validate_ok,
)

class TestTb3WaveSealBindings:
    def test_hidden_plan_seal_required(self):
        """Hidden fixture requires plan-seal plan_hash equal to rollback-plan embedded hash field."""
        hidden = json.loads(
            (Path(__file__).resolve().parent / "verifier-fixtures" / "tb3-wave-seal-bindings.json").read_text()
        )
        _rebuild_ctl()
        _run(["/app/bin/rollbackctl", "inspect"])
        _run(["/app/bin/rollbackctl", "plan"])
        seal = json.loads(Path(PATH_PLAN_SEAL).read_text())
        plan = json.loads(Path(PATH_ROLLBACK_PLAN).read_text())
        assert hidden["seal_field"] in seal
        assert seal[hidden["seal_field"]] == plan["hash"]

    def test_hidden_registry_release_from_fixture(self):
        """Hidden fixture incident_id must match inspect-manifest registry_release binding."""
        hidden = json.loads(
            (Path(__file__).resolve().parent / "verifier-fixtures" / "tb3-registry-bindings.json").read_text()
        )
        _rebuild_ctl()
        _run(["/app/bin/rollbackctl", "inspect"])
        manifest = json.loads(Path(PATH_INSPECT_MANIFEST).read_text())
        reg = json.loads(Path(PATH_INCIDENT_REGISTRY).read_text())
        assert manifest["registry_release"] == reg[hidden["incident_id"]]["release"]


class TestTb3IncidentTraps:
    """TB3 hidden incident probes — not duplicated in instruction prose."""

    @pytest.fixture(autouse=True)
    def pipeline(self):
        _rebuild_ctl()
        _run(["/app/bin/rollbackctl", "inspect"])
        _run(["/app/bin/rollbackctl", "plan"])

    def test_hidden_incident_fixture_matches_release(self):
        """Hidden probe: rollbackctl inspect stages incident_id and failed billing-core from release truth."""
        hidden = json.loads((Path(__file__).resolve().parent / "verifier-fixtures" / "tb3-incident-trap.json").read_text())
        status = json.loads((APP / "state/deploy-status.json").read_text())
        assert status["incident_id"] == hidden["incident_id"]
        assert status["services"]["billing-core"]["status"] == "failed"

    def test_hidden_plan_steps_match_graph_reversal(self):
        """Hidden incident probe expects graph-derived rollback order from rollbackctl plan."""
        plan = json.loads((APP / "output/rollback-plan.json").read_text())
        assert plan["steps"] == reference_rollback_steps()

    def test_hidden_failed_service_not_in_plan(self):
        """Failed billing-core from inspect midpipe must stay absent from rollbackctl plan."""
        status = json.loads((APP / "state/deploy-status.json").read_text())
        failed = [s for s, v in status["services"].items() if v["status"] == "failed"][0]
        plan = json.loads((APP / "output/rollback-plan.json").read_text())
        assert failed not in plan["steps"]

    def test_hidden_delayed_log_identity_gate_from_verifier_fixture(self):
        """Hidden delayed log probe: rollbackctl inspect keeps identity-gate updated from release truth."""
        hidden = json.loads((Path(__file__).resolve().parent / "verifier-fixtures" / "tb3-delayed-log-trap.json").read_text())
        assert isinstance(hidden.get("probe"), str) and hidden["probe"]
        status = json.loads((APP / "state/deploy-status.json").read_text())
        assert status["services"]["identity-gate"]["status"] == "updated"


class TestServiceClosurePolicy:
    def test_rollback_graph_has_no_cycle(self):
        """rollbackctl validate accepts the live acyclic topology after plan emit."""
        _rebuild_ctl()
        _run(["/app/bin/rollbackctl", "inspect"])
        _run(["/app/bin/rollbackctl", "plan"])
        proc = _run(["/app/bin/rollbackctl", "validate"])
        assert proc.returncode == 0, proc.stderr

    def test_closure_rejects_cyclic_service_fixture(self):
        """rollbackctl validate --graph must reject verifier cyclic topology fixture."""
        cycle = str(Path(__file__).resolve().parent / "verifier-fixtures" / "tb3-cyclic-closure.json")
        proc = _run(["/app/bin/rollbackctl", "validate", "--graph", cycle])
        assert proc.returncode != 0

    def test_alert_dispatch_rolls_back_before_identity_gate(self):
        """rollbackctl plan orders alert-dispatch before identity-gate per graph dependents-first policy."""
        _rebuild_ctl()
        _run(["/app/bin/rollbackctl", "inspect"])
        proc = _run(["/app/bin/rollbackctl", "plan"])
        assert proc.returncode == 0, proc.stderr + proc.stdout
        plan = json.loads(Path(PATH_ROLLBACK_PLAN).read_text())
        pos = {svc: i for i, svc in enumerate(plan["steps"])}
        assert pos["alert-dispatch"] < pos["identity-gate"]
        assert "billing-core" not in plan["steps"]

    def test_inspect_registry_release_matches_incident(self):
        """rollbackctl inspect registry_release matches incident registry for staged incident_id."""
        _rebuild_ctl()
        proc = _run(["/app/bin/rollbackctl", "inspect"])
        assert proc.returncode == 0, proc.stderr + proc.stdout
        reg = json.loads(Path(PATH_INCIDENT_REGISTRY).read_text())
        status = json.loads((APP / "state/deploy-status.json").read_text())
        manifest = json.loads(Path(PATH_INSPECT_MANIFEST).read_text())
        assert manifest["registry_release"] == reg[status["incident_id"]]["release"]
        assert reg[status["incident_id"]]["failed_service"] == "billing-core"

    def test_plan_reverses_forward_deploy_bookends(self):
        """rollbackctl plan puts forward-order last service first among updated rollback steps."""
        _rebuild_ctl()
        _run(["/app/bin/rollbackctl", "inspect"])
        proc = _run(["/app/bin/rollbackctl", "plan"])
        assert proc.returncode == 0, proc.stderr + proc.stdout
        order = json.loads((APP / "data/deploy/forward-order.json").read_text())
        plan = json.loads(Path(PATH_ROLLBACK_PLAN).read_text())
        assert order[0] == "ledger-db"
        assert order[-1] == "alert-dispatch"
        assert plan["steps"][0] == "alert-dispatch"
        assert plan["steps"][-1] == "ledger-db"

    def test_plan_emit_matches_wave_schema_fields(self):
        """rollbackctl plan emit carries wave-egress-schema hash and steps fields."""
        _rebuild_ctl()
        _run(["/app/bin/rollbackctl", "inspect"])
        proc = _run(["/app/bin/rollbackctl", "plan"])
        assert proc.returncode == 0, proc.stderr + proc.stdout
        plan = json.loads(Path(PATH_ROLLBACK_PLAN).read_text())
        assert isinstance(plan.get("steps"), list) and plan["steps"]
        assert isinstance(plan.get("hash"), str) and len(plan["hash"]) == 64
        seal = json.loads(Path(PATH_PLAN_SEAL).read_text())
        assert seal["plan_hash"] == plan["hash"]


class TestMisleadingEventLog:
    def test_inspect_ignores_corrupt_event_log_lines(self):
        """rollbackctl inspect still stages deploy-status when rollback-events.jsonl has corrupt JSON."""
        _rebuild_ctl()
        proc = _run(["/app/bin/rollbackctl", "inspect"])
        assert proc.returncode == 0, proc.stderr + proc.stdout
        status = json.loads((APP / "state/deploy-status.json").read_text())
        assert "billing-core" in status["services"]

    def test_inspect_rejects_corrupt_log_billing_complete_claim(self):
        """rollbackctl inspect keeps billing-core failed despite corrupt log rollback_complete claim."""
        _rebuild_ctl()
        proc = _run(["/app/bin/rollbackctl", "inspect"])
        assert proc.returncode == 0, proc.stderr + proc.stdout
        status = json.loads((APP / "state/deploy-status.json").read_text())
        assert status["services"]["billing-core"]["status"] == "failed"

class TestWaveApplyRuntime:
    @pytest.fixture(autouse=True)
    def full_apply(self):
        _rebuild_ctl()
        _run(["/app/bin/rollbackctl", "inspect"])
        _run(["/app/bin/rollbackctl", "plan"])
        validate_ok()
        marker = APP / "state/rollback-complete.ok"
        if marker.is_file():
            marker.unlink()
        proc = _run(
            ["bash", "/app/deploy/scripts/apply-rollback.sh"],
            env={"ROLLBACK_INCIDENT_ID": "inc-4429", "ROLLBACK_ZONE": "primary"},
        )
        assert proc.returncode == 0, proc.stderr + proc.stdout

    def test_rollback_complete_marker(self):
        """rollback-complete.ok must exist after apply-rollback succeeds."""
        marker = APP / "state/rollback-complete.ok"
        assert marker.is_file()
        assert marker.read_text(encoding="utf-8").strip() == "ok"

    def test_plan_not_hardcoded_placeholder(self):
        """Rollback plan hash must not be a placeholder constant."""
        plan = json.loads((APP / "output/rollback-plan.json").read_text())
        assert "deadbeef" not in plan["hash"].lower()
        assert len(plan["hash"]) == 64

    def test_lane_hint_shim_alone_fails(self):
        """Patching only internal/im_dec shim cannot satisfy full rollback plan."""
        plan = json.loads((APP / "output/rollback-plan.json").read_text())
        assert plan["steps"][0] == "alert-dispatch"
        assert len(plan["steps"]) == 3

    def test_forward_lane_decoy_alone_fails(self):
        """Reading deploy/deploy-priority.json decoy cannot replace graph rollback plan."""
        decoy = json.loads((APP / "deploy/deploy-priority.json").read_text())
        plan = json.loads((APP / "output/rollback-plan.json").read_text())
        assert decoy[0] == "ledger-db"
        assert plan["steps"] == reference_rollback_steps()

    def test_apply_requires_plan_seal(self):
        """apply-rollback must fail when plan-seal.json is missing after emit."""
        seal = Path(PATH_PLAN_SEAL)
        if seal.is_file():
            seal.unlink()
        proc = _run(
            ["bash", "/app/deploy/scripts/apply-rollback.sh"],
            env={"ROLLBACK_INCIDENT_ID": "inc-4429", "ROLLBACK_ZONE": "primary"},
        )
        assert proc.returncode != 0

    def test_apply_rejects_stale_manifest_release_digest(self):
        """apply-rollback must fail when deploy-status no longer matches inspect-manifest."""
        manifest = Path(PATH_INSPECT_MANIFEST)
        data = json.loads(manifest.read_text())
        saved = manifest.read_text()
        data["release_digest"] = "0" * 64
        manifest.write_text(json.dumps(data, indent=2))
        proc = _run(
            ["bash", "/app/deploy/scripts/apply-rollback.sh"],
            env={"ROLLBACK_INCIDENT_ID": "inc-4429", "ROLLBACK_ZONE": "primary"},
        )
        assert proc.returncode != 0
        manifest.write_text(saved)


class TestCtlBinaryRebuild:
    def test_rebuild_ctl_from_go_sources(self):
        """After rebuild, rollbackctl inspect runs and writes deploy-status midpipe."""
        _rebuild_ctl()
        proc = _run(["/app/bin/rollbackctl", "inspect"])
        assert proc.returncode == 0, proc.stderr + proc.stdout
        assert (APP / "state/deploy-status.json").is_file()
