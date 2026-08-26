"""Rollback wave contract tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from test_outputs import (
    APP,
    PATH_DEPLOY_STATUS,
    PATH_FORWARD_ORDER,
    PATH_INCIDENT_REGISTRY,
    PATH_INSPECT_MANIFEST,
    PATH_PLAN_SEAL,
    PATH_ROLLBACK_COMPLETE,
    PATH_ROLLBACK_PLAN,
    PATH_TRUTH_LEDGER,
    PATH_EGRESS_LANE,
    PATH_RUN_LEDGER,
    PATH_WITNESS_BUNDLE,
    SERVICES,
    _rebuild_ctl,
    _run,
    reference_deploy_status,
    reference_forward_digest,
    reference_plan_hash,
    reference_release_digest,
    reference_release_digest_lexsort,
    reference_rollback_steps,
    validate_ok,
)

class TestRollbackArtifactAnchors:
    """Each instruction-cited path is proven via rollbackctl midpipe and emit behavior."""

    def test_inspect_binds_incident_registry_release(self):
        """rollbackctl inspect binds registry_release from incident registry for live incident_id."""
        _rebuild_ctl()
        proc = _run(["/app/bin/rollbackctl", "inspect"])
        assert proc.returncode == 0, proc.stderr + proc.stdout
        reg = json.loads(Path(PATH_INCIDENT_REGISTRY).read_text())
        status = json.loads(Path(PATH_DEPLOY_STATUS).read_text())
        manifest = json.loads(Path(PATH_INSPECT_MANIFEST).read_text())
        assert status["incident_id"] == "inc-4429"
        assert manifest["registry_release"] == reg["inc-4429"]["release"]

    def test_inspect_truth_source_is_release_state(self):
        """rollbackctl inspect uses release-state as truth_source on inspect-manifest."""
        _rebuild_ctl()
        proc = _run(["/app/bin/rollbackctl", "inspect"])
        assert proc.returncode == 0, proc.stderr + proc.stdout
        manifest = json.loads(Path(PATH_INSPECT_MANIFEST).read_text())
        assert manifest["truth_source"] == "release-state"
        assert "incident_id" in json.loads(Path(PATH_DEPLOY_STATUS).read_text())

    def test_inspect_forward_digest_covers_four_service_order(self):
        """rollbackctl inspect forward_digest binds the four-service forward-order sequence."""
        _rebuild_ctl()
        proc = _run(["/app/bin/rollbackctl", "inspect"])
        assert proc.returncode == 0, proc.stderr + proc.stdout
        order = json.loads(Path(PATH_FORWARD_ORDER).read_text())
        manifest = json.loads(Path(PATH_INSPECT_MANIFEST).read_text())
        assert len(order) == 4
        assert manifest["forward_digest"] == reference_forward_digest()

    def test_plan_includes_graph_dependent_ledger_db(self):
        """rollbackctl plan includes ledger-db from topology rollback graph reversal."""
        _rebuild_ctl()
        _run(["/app/bin/rollbackctl", "inspect"])
        proc = _run(["/app/bin/rollbackctl", "plan"])
        assert proc.returncode == 0, proc.stderr + proc.stdout
        plan = json.loads(Path(PATH_ROLLBACK_PLAN).read_text())
        assert "ledger-db" in plan["steps"]

    def test_inspect_succeeds_despite_corrupt_event_log(self):
        """rollbackctl inspect exits 0 and stages deploy-status even when event log has corrupt lines."""
        _rebuild_ctl()
        proc = _run(["/app/bin/rollbackctl", "inspect"])
        assert proc.returncode == 0, proc.stderr + proc.stdout
        assert Path(PATH_DEPLOY_STATUS).is_file()
        status = json.loads(Path(PATH_DEPLOY_STATUS).read_text())
        assert status["services"]["billing-core"]["status"] == "failed"

    def test_deploy_status_output_path(self):
        """Success criteria require /app/state/deploy-status.json midpipe snapshot."""
        _rebuild_ctl()
        proc = _run(["/app/bin/rollbackctl", "inspect"])
        assert proc.returncode == 0, proc.stderr + proc.stdout
        assert Path(PATH_DEPLOY_STATUS).is_file()
        assert Path(PATH_INSPECT_MANIFEST).is_file()

    def test_rollback_plan_output_path(self):
        """Success criteria require /app/output/rollback-plan.json emit."""
        _rebuild_ctl()
        _run(["/app/bin/rollbackctl", "inspect"])
        proc = _run(["/app/bin/rollbackctl", "plan"])
        assert proc.returncode == 0, proc.stderr + proc.stdout
        plan = json.loads(Path(PATH_ROLLBACK_PLAN).read_text())
        assert plan["steps"]

    def test_rollback_complete_marker_path(self):
        """Success criteria require /app/state/rollback-complete.ok after apply."""
        _rebuild_ctl()
        _run(["/app/bin/rollbackctl", "inspect"])
        _run(["/app/bin/rollbackctl", "plan"])
        validate_ok()
        marker = Path(PATH_ROLLBACK_COMPLETE)
        if marker.is_file():
            marker.unlink()
        proc = _run(
            ["bash", "/app/deploy/scripts/apply-rollback.sh"],
            env={"ROLLBACK_INCIDENT_ID": "inc-4429", "ROLLBACK_ZONE": "primary"},
        )
        assert proc.returncode == 0, proc.stderr + proc.stdout
        assert marker.is_file()

    def test_truth_ledger_midpipe_path(self):
        """rollback-policy.md requires /app/state/truth-ledger.json after inspect."""
        _rebuild_ctl()
        proc = _run(["/app/bin/rollbackctl", "inspect"])
        assert proc.returncode == 0, proc.stderr + proc.stdout
        assert Path(PATH_TRUTH_LEDGER).is_file()
        ledger = json.loads(Path(PATH_TRUTH_LEDGER).read_text())
        assert ledger.get("capture_sequence", 0) >= 1

    def test_egress_lane_midpipe_path(self):
        """instruction.md requires /app/state/egress-lane-midpipe.json after plan."""
        _rebuild_ctl()
        _run(["/app/bin/rollbackctl", "inspect"])
        proc = _run(["/app/bin/rollbackctl", "plan"])
        assert proc.returncode == 0, proc.stderr + proc.stdout
        assert Path(PATH_EGRESS_LANE).is_file()

    def test_witness_bundle_midpipe_path(self):
        """witness-quorum-spec.md requires rollback-witness-bundle.json after validate."""
        _rebuild_ctl()
        _run(["/app/bin/rollbackctl", "inspect"])
        _run(["/app/bin/rollbackctl", "plan"])
        validate_ok()
        assert Path(PATH_WITNESS_BUNDLE).is_file()

    def test_rollback_run_ledger_path(self):
        """Successful apply writes rollback-run-ledger.json with apply_epoch, last_plan_hash, last_capture_sequence."""
        _rebuild_ctl()
        _run(["/app/bin/rollbackctl", "inspect"])
        _run(["/app/bin/rollbackctl", "plan"])
        validate_ok()
        marker = Path(PATH_ROLLBACK_COMPLETE)
        ledger_path = Path(PATH_RUN_LEDGER)
        if marker.is_file():
            marker.unlink()
        if ledger_path.is_file():
            ledger_path.unlink()
        plan = json.loads(Path(PATH_ROLLBACK_PLAN).read_text())
        manifest = json.loads(Path(PATH_INSPECT_MANIFEST).read_text())
        proc = _run(
            ["bash", "/app/deploy/scripts/apply-rollback.sh"],
            env={"ROLLBACK_INCIDENT_ID": "inc-4429", "ROLLBACK_ZONE": "primary"},
        )
        assert proc.returncode == 0, proc.stderr + proc.stdout
        assert ledger_path.is_file()
        ledger = json.loads(ledger_path.read_text())
        assert ledger["apply_epoch"] == 1
        assert ledger["last_plan_hash"] == plan["hash"]
        assert ledger["last_capture_sequence"] == manifest["capture_sequence"]

    def test_incident_registry_authoritative_input(self):
        """instruction.md cites /app/data/incident/registry.json for registry_release binding."""
        _rebuild_ctl()
        proc = _run(["/app/bin/rollbackctl", "inspect"])
        assert proc.returncode == 0, proc.stderr + proc.stdout
        reg = json.loads(Path(PATH_INCIDENT_REGISTRY).read_text())
        manifest = json.loads(Path(PATH_INSPECT_MANIFEST).read_text())
        status = json.loads(Path(PATH_DEPLOY_STATUS).read_text())
        assert manifest["registry_release"] == reg[status["incident_id"]]["release"]


class TestBundledReleaseTruth:
    def test_billing_core_failed_in_release_state(self):
        """rollbackctl inspect stages billing-core as failed from release truth."""
        _rebuild_ctl()
        proc = _run(["/app/bin/rollbackctl", "inspect"])
        assert proc.returncode == 0, proc.stderr + proc.stdout
        status = json.loads(Path(PATH_DEPLOY_STATUS).read_text())
        assert status["services"]["billing-core"]["status"] == "failed"

    def test_three_services_updated(self):
        """rollbackctl inspect stages three updated services from partial deploy truth."""
        _rebuild_ctl()
        proc = _run(["/app/bin/rollbackctl", "inspect"])
        assert proc.returncode == 0, proc.stderr + proc.stdout
        status = json.loads(Path(PATH_DEPLOY_STATUS).read_text())
        updated = [s for s, v in status["services"].items() if v["status"] == "updated"]
        assert set(updated) == {"ledger-db", "identity-gate", "alert-dispatch"}

class TestWaveDependencyOrder:
    def test_plan_steps_reverse_dependencies(self):
        """dependency-graph.md requires dependents rolled back before dependencies."""
        _rebuild_ctl()
        _run(["/app/bin/rollbackctl", "inspect"])
        _run(["/app/bin/rollbackctl", "plan"])
        order = json.loads((APP / "output/rollback-plan.json").read_text())["steps"]
        graph = json.loads((APP / "data/topology/rollback-graph.json").read_text())
        pos = {svc: i for i, svc in enumerate(order)}
        for svc in order:
            for dep in graph.get(svc, []):
                if dep in pos and pos[dep] < pos[svc]:
                    pytest.fail(f"{dep} before dependent {svc} in rollback plan")


class TestPartitionWitness:
    def test_incident_id_required_for_apply(self):
        """wave-egress-schema.md requires ROLLBACK_INCIDENT_ID before apply-rollback."""
        _rebuild_ctl()
        _run(["/app/bin/rollbackctl", "inspect"])
        _run(["/app/bin/rollbackctl", "plan"])
        validate_ok()
        proc = _run(["bash", "/app/deploy/scripts/apply-rollback.sh"])
        assert proc.returncode != 0

    def test_incident_id_wrong_value_rejected_for_apply(self):
        """wave-egress-schema.md rejects wrong ROLLBACK_INCIDENT_ID not matching deploy-status incident_id."""
        _rebuild_ctl()
        _run(["/app/bin/rollbackctl", "inspect"])
        _run(["/app/bin/rollbackctl", "plan"])
        validate_ok()
        proc = _run(
            ["bash", "/app/deploy/scripts/apply-rollback.sh"],
            env={"ROLLBACK_INCIDENT_ID": "inc-9999", "ROLLBACK_ZONE": "primary"},
        )
        assert proc.returncode != 0

    def test_rollback_zone_primary_required_for_apply(self):
        """partition-recovery requires ROLLBACK_ZONE=primary during apply."""
        _rebuild_ctl()
        _run(["/app/bin/rollbackctl", "inspect"])
        _run(["/app/bin/rollbackctl", "plan"])
        validate_ok()
        proc = _run(
            ["bash", "/app/deploy/scripts/apply-rollback.sh"],
            env={"ROLLBACK_INCIDENT_ID": "inc-4429", "ROLLBACK_ZONE": "secondary"},
        )
        assert proc.returncode != 0


class TestReleaseTruthCapture:
    @pytest.fixture(autouse=True)
    def rebuild(self):
        _rebuild_ctl()

    def test_inspect_ignores_corrupt_log_for_billing(self):
        """rollbackctl inspect writes midpipe deploy-status snapshot from release truth."""
        proc = _run(["/app/bin/rollbackctl", "inspect"])
        assert proc.returncode == 0, proc.stderr
        status = json.loads((APP / "state/deploy-status.json").read_text())
        assert status["services"]["billing-core"]["status"] == "failed"

    def test_inspect_ignores_delayed_log_for_identity_gate(self):
        """midpipe deploy-status must keep identity-gate updated despite delayed deploy_failed log."""
        _run(["/app/bin/rollbackctl", "inspect"])
        status = json.loads((APP / "state/deploy-status.json").read_text())
        assert status["services"]["identity-gate"]["status"] == "updated"

    def test_inspect_preserves_alert_dispatch_updated(self):
        """midpipe deploy-status must keep alert-dispatch updated despite delayed deploy_failed log."""
        _run(["/app/bin/rollbackctl", "inspect"])
        status = json.loads((APP / "state/deploy-status.json").read_text())
        assert status["services"]["alert-dispatch"]["status"] == "updated"

    def test_inspect_writes_midpipe_manifest(self):
        """inspect must write /app/state/inspect-manifest.json with truth_source release-state."""
        manifest_path = Path(PATH_INSPECT_MANIFEST)
        if manifest_path.is_file():
            manifest_path.unlink()
        proc = _run(["/app/bin/rollbackctl", "inspect"])
        assert proc.returncode == 0, proc.stderr
        manifest = json.loads(manifest_path.read_text())
        assert manifest["truth_source"] == "release-state"
        assert len(manifest.get("release_digest", "")) == 64
        assert manifest.get("forward_digest") == reference_forward_digest()
        reg = json.loads(Path(PATH_INCIDENT_REGISTRY).read_text())
        status = json.loads((APP / "state/deploy-status.json").read_text())
        assert manifest.get("registry_release") == reg[status["incident_id"]]["release"]
        ledger_path = APP / "state/truth-ledger.json"
        assert ledger_path.is_file()
        ledger = json.loads(ledger_path.read_text())
        assert manifest.get("capture_sequence") == ledger.get("capture_sequence")

    def test_inspect_manifest_forward_digest_matches(self):
        """inspect-manifest forward_digest must bind forward-order.json sequence."""
        _run(["/app/bin/rollbackctl", "inspect"])
        manifest = json.loads(Path(PATH_INSPECT_MANIFEST).read_text())
        assert manifest["forward_digest"] == reference_forward_digest()

    def test_release_digest_forward_order_not_lexicographic(self):
        """release_digest uses forward-order sequence, not lexicographic service sort."""
        status = reference_deploy_status()
        lex_digest = reference_release_digest_lexsort(status)
        _run(["/app/bin/rollbackctl", "inspect"])
        manifest = json.loads(Path(PATH_INSPECT_MANIFEST).read_text())
        assert manifest["release_digest"] != lex_digest
        assert manifest["release_digest"] == reference_release_digest(status)

    def test_deploy_status_matches_release_state(self):
        """midpipe deploy-status.json snapshot must mirror release-state outcomes."""
        _run(["/app/bin/rollbackctl", "inspect"])
        status = json.loads((APP / "state/deploy-status.json").read_text())
        ref = reference_deploy_status()
        for svc in SERVICES:
            assert status["services"][svc]["status"] == ref["services"][svc]["status"]

    def test_incident_id_preserved(self):
        """inspect preserves incident_id inc-4429 from release state."""
        _run(["/app/bin/rollbackctl", "inspect"])
        status = json.loads((APP / "state/deploy-status.json").read_text())
        assert status["incident_id"] == "inc-4429"


class TestWaveEgressChain:
    @pytest.fixture(autouse=True)
    def pipeline(self):
        _rebuild_ctl()
        _run(["/app/bin/rollbackctl", "inspect"])
        _run(["/app/bin/rollbackctl", "plan"])

    def test_plan_requires_inspect_manifest(self):
        """plan must refuse when /app/state/inspect-manifest.json is missing."""
        manifest = Path(PATH_INSPECT_MANIFEST)
        assert manifest.is_file()
        saved = manifest.read_text()
        manifest.unlink()
        proc = _run(["/app/bin/rollbackctl", "plan"])
        assert proc.returncode != 0
        manifest.write_text(saved)

    def test_plan_rejects_wrong_manifest_truth_source(self):
        """plan must refuse when inspect-manifest truth_source is not release-state."""
        manifest = Path(PATH_INSPECT_MANIFEST)
        data = json.loads(manifest.read_text())
        saved = manifest.read_text()
        data["truth_source"] = "rollback-log"
        manifest.write_text(json.dumps(data, indent=2))
        proc = _run(["/app/bin/rollbackctl", "plan"])
        assert proc.returncode != 0
        manifest.write_text(saved)

    def test_plan_rejects_wrong_forward_digest(self):
        """plan must refuse when inspect-manifest forward_digest does not match forward-order."""
        manifest = Path(PATH_INSPECT_MANIFEST)
        data = json.loads(manifest.read_text())
        saved = manifest.read_text()
        data["forward_digest"] = "0" * 64
        manifest.write_text(json.dumps(data, indent=2))
        proc = _run(["/app/bin/rollbackctl", "plan"])
        assert proc.returncode != 0
        manifest.write_text(saved)

    def test_plan_recomputes_forward_digest_binding(self):
        """plan must recompute forward_digest from forward-order.json and match manifest."""
        manifest = json.loads(Path(PATH_INSPECT_MANIFEST).read_text())
        assert manifest["forward_digest"] == reference_forward_digest()
        proc = _run(["/app/bin/rollbackctl", "plan"])
        assert proc.returncode == 0, proc.stderr

    def test_plan_recomputes_registry_release_binding(self):
        """plan must reload registry.json for incident_id and match manifest registry_release."""
        manifest = json.loads(Path(PATH_INSPECT_MANIFEST).read_text())
        status = json.loads((APP / "state/deploy-status.json").read_text())
        reg = json.loads(Path(PATH_INCIDENT_REGISTRY).read_text())
        assert manifest["registry_release"] == reg[status["incident_id"]]["release"]
        proc = _run(["/app/bin/rollbackctl", "plan"])
        assert proc.returncode == 0, proc.stderr

    def test_plan_rejects_stale_registry_release(self):
        """plan must refuse when inspect-manifest registry_release disagrees with incident registry."""
        manifest = Path(PATH_INSPECT_MANIFEST)
        data = json.loads(manifest.read_text())
        saved = manifest.read_text()
        data["registry_release"] = "rel-stale"
        manifest.write_text(json.dumps(data, indent=2))
        proc = _run(["/app/bin/rollbackctl", "plan"])
        assert proc.returncode != 0
        manifest.write_text(saved)

    def test_manifest_digest_matches_deploy_status(self):
        """inspect-manifest release_digest must match deploy-status service statuses."""
        manifest = json.loads(Path(PATH_INSPECT_MANIFEST).read_text())
        status = json.loads((APP / "state/deploy-status.json").read_text())
        assert manifest["release_digest"] == reference_release_digest(status)

    def test_plan_ignores_poison_rollback_order_file(self):
        """plan must compute steps from deploy-status and graph, not rollback-order.json."""
        order_path = APP / "deploy/rollback-order.json"
        saved = order_path.read_text()
        order_path.write_text(json.dumps(["ledger-db", "identity-gate", "alert-dispatch"]))
        proc = _run(["/app/bin/rollbackctl", "plan"])
        assert proc.returncode == 0, proc.stderr
        plan = json.loads((APP / "output/rollback-plan.json").read_text())
        assert plan["steps"] == reference_rollback_steps()
        order_path.write_text(saved)

    def test_apply_ignores_poison_rollback_order_file(self):
        """apply-rollback uses rollback-plan.json only; stale rollback-order.json may stay poisoned."""
        order_path = APP / "deploy/rollback-order.json"
        poison = json.loads(order_path.read_text())
        assert "billing-core" in poison
        marker = APP / "state/rollback-complete.ok"
        if marker.is_file():
            marker.unlink()
        validate_ok()
        proc = _run(
            ["bash", "/app/deploy/scripts/apply-rollback.sh"],
            env={"ROLLBACK_INCIDENT_ID": "inc-4429", "ROLLBACK_ZONE": "primary"},
        )
        assert proc.returncode == 0, proc.stderr + proc.stdout
        assert marker.read_text(encoding="utf-8").strip() == "ok"

    def test_plan_excludes_failed_billing_core(self):
        """Failed billing-core must not appear in rollback-plan steps."""
        plan = json.loads((APP / "output/rollback-plan.json").read_text())
        assert "billing-core" not in plan["steps"]

    def test_plan_steps_match_reference(self):
        """rollback-policy.md defines alert-dispatch → identity-gate → ledger-db."""
        plan = json.loads((APP / "output/rollback-plan.json").read_text())
        assert plan["steps"] == reference_rollback_steps()

    def test_reference_plan_hash_matches_truth_lines(self):
        """Emit hash must follow wave-egress-schema sorted line rules."""
        plan = json.loads((APP / "output/rollback-plan.json").read_text())
        expected = reference_plan_hash(plan["steps"], plan["release"])
        assert plan["hash"] == expected

    def test_wave_validate_accepts_safe_order(self):
        """validate subcommand accepts dependency-safe rollback order."""
        proc = _run(["/app/bin/rollbackctl", "validate"])
        assert proc.returncode == 0, proc.stderr

    def test_validate_requires_plan_seal_binding(self):
        """validate must refuse when plan-seal.json is missing."""
        seal = Path(PATH_PLAN_SEAL)
        saved = seal.read_text() if seal.is_file() else None
        if seal.is_file():
            seal.unlink()
        proc = _run(["/app/bin/rollbackctl", "validate"])
        assert proc.returncode != 0
        if saved is not None:
            seal.write_text(saved)

    def test_validate_rejects_stale_manifest_digest(self):
        """validate must refuse when inspect-manifest release_digest is stale."""
        manifest = Path(PATH_INSPECT_MANIFEST)
        data = json.loads(manifest.read_text())
        saved = manifest.read_text()
        data["release_digest"] = "0" * 64
        manifest.write_text(json.dumps(data, indent=2))
        proc = _run(["/app/bin/rollbackctl", "validate"])
        assert proc.returncode != 0
        manifest.write_text(saved)

    def test_emit_writes_plan_seal(self):
        """plan emit writes plan-seal plan_hash equal to rollback-plan embedded hash field."""
        plan = json.loads(Path(PATH_ROLLBACK_PLAN).read_text())
        seal = json.loads(Path(PATH_PLAN_SEAL).read_text())
        assert seal["plan_hash"] == plan["hash"]
        assert seal["seal"] == "rollback-bound"

    def test_plan_fails_after_inspect_only(self):
        """plan must fail when deploy-status midpipe is removed after inspect."""
        status = Path(PATH_DEPLOY_STATUS)
        saved = status.read_text()
        status.unlink()
        proc = _run(["/app/bin/rollbackctl", "plan"])
        assert proc.returncode != 0
        status.write_text(saved)
